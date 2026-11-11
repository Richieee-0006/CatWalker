#!/usr/bin/env python3
"""
CatWalker - Automatic application categorization for Walker using LLM
"""

import argparse
import logging
import sys
import os
import shutil
import subprocess

from categorizer import AppCategorizer
from config import DEFAULT_CATEGORIES, REVERSE_CATEGORY_MAPPING, WALKER_MENUS_DIR
from config import GEMINI_API_KEY
from parser import DesktopFileParser
from writer import DesktopFileWriter
from menu_generator import MenuGenerator
from db_sync import DatabaseSynchronizer

logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def cmd_scan(args):
    """Scan and display applications"""
    parser = DesktopFileParser()
    entries = parser.scan_all()

    print(f"\n{'=' * 70}")
    print(f"Total applications found: {len(entries)}")
    print(f"{'=' * 70}\n")

    if args.uncategorized:
        entries = parser.get_uncategorized()
        print(f"Uncategorized applications: {len(entries)}\n")

    if args.category:
        entries = parser.get_by_category(args.category)
        print(f"Applications in '{args.category}': {len(entries)}\n")

    for i, (filename, entry) in enumerate(entries.items(), 1):
        if args.limit and i > args.limit:
            print(f"\n... and {len(entries) - args.limit} more")
            break

        print(f"{i}. {entry.name}")
        print(f"   File: {filename}")
        if entry.comment:
            print(f"   Info: {entry.comment}")
        if entry.categories:
            print(f"   Categories: {', '.join(entry.categories)}")
        else:
            print(f"   Categories: (none)")
        print()


def cmd_categorize(args):
    """Categorize applications using LLM"""
    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set. Please set it with: export GEMINI_API_KEY='your-api-key'")
        return 1

    parser = DesktopFileParser()
    entries = parser.scan_all()

    if args.recategorize:
        logger.info(f"Re-categorizing all {len(entries)} applications")
    else:
        # Categorize if it has NO categories OR it's only in system directory
        # (meaning we haven't processed it and overridden it in user dir yet)
        uncategorized = parser.get_uncategorized()
        system_only = parser.get_system_only()
        
        # Merge them
        entries = {**uncategorized, **system_only}
        logger.info(f"Categorizing {len(entries)} uncategorized applications ({len(uncategorized)} empty, {len(system_only)} system-only)")

    if not entries:
        logger.info("No applications to categorize")
        return 0

    if args.limit:
        entries = dict(list(entries.items())[:args.limit])
        logger.info(f"Limited to {args.limit} applications for testing")

    logger.info("Sending to Gemini API...")
    categorizer = AppCategorizer()
    categorization = categorizer.categorize(entries, batch_size=args.batch_size)

    if not categorization:
        logger.error("Categorization failed")
        return 1

    # Show results
    print(f"\n{'=' * 70}")
    print("Categorization Results")
    print(f"{'=' * 70}\n")

    for filename, category in categorization.items():
        entry = entries[filename]
        old_cats = ', '.join(entry.categories) if entry.categories else 'None'
        print(f"{entry.name}")
        print(f"  {old_cats} → {category}")

    # Apply .desktop file changes
    writer = DesktopFileWriter(dry_run=args.dry_run)

    print(f"\n{'=' * 70}")
    if not args.dry_run:
        print("Applying changes...")
        confirm = input("\nProceed? [y/N] ")
        if confirm.lower() != 'y':
            print("Cancelled")
            return 0
    else:
        print("DRY RUN - No changes will be made")

    print(f"{'=' * 70}\n")

    results = writer.apply_categorization(entries, categorization)
    success_count = sum(1 for v in results.values() if v)

    print(f"\n{'=' * 70}")
    print(f"Complete: {success_count}/{len(results)} files processed")
    if not args.dry_run:
        print(f"Backup saved: {writer.backup_timestamp}")
        print("✓ Restarting services...")
        _restart_walker_services()
    print(f"{'=' * 70}")

    return 0


def cmd_menus(args):
    """Generate Elephant menu files from categorized apps"""
    if args.clean:
        gen = MenuGenerator()
        gen.cleanup()
        print("✓ Removed CatWalker menu files")
        _restart_walker_services()
        return 0

    # We need all categorized apps - scan and use existing categories
    parser = DesktopFileParser()
    entries = parser.scan_all()

    # Build categorization from existing .desktop categories
    categorized = {}
    uncategorized_count = 0
    for filename, entry in entries.items():
        if not entry.categories:
            uncategorized_count += 1
            continue
        # Map freedesktop categories back to our categories
        cat = _map_desktop_category(entry.categories, filename)
        if cat:
            categorized[filename] = cat
        else:
            uncategorized_count += 1

    if not categorized:
        logger.error("No categorized apps found. Run 'categorize --apply' first.")
        return 1

    if uncategorized_count > 0 and not args.quiet:
        logger.warning(f"{uncategorized_count} applications are uncategorized and will be missing from menus.")
        print(f"Suggestion: Run './catwalker categorize --apply' to include them.")

    if not args.quiet:
        print(f"\nFound {len(categorized)} categorized applications")

    gen = MenuGenerator()

    if args.dry_run:
        gen.generate(categorized, entries, dry_run=True)
        print("\nUse without --dry-run to actually generate files")
        return 0

    if gen.generate(categorized, entries):
        if not args.quiet:
            print(f"\n{'=' * 70}")
            print(f"✓ Menu files generated in {WALKER_MENUS_DIR}")
            print("✓ Walker configuration updated")
            print("✓ Restarting services...")
            print(f"{'=' * 70}")
            # Only restart services if not quiet (manual run)
            _restart_walker_services()
        
        # Automatically sync to DB as well
        try:
            db = DatabaseSynchronizer()
            if db.init_db():
                usage_data = gen._get_usage_data()
                db.sync(entries, usage_data, categorized)
        except Exception as e:
            logger.debug(f"DB sync failed during menu refresh: {e}")
            
        return 0
    return 1


def _restart_walker_services():
    """Restarts Walker and Elephant services using omarchy-restart-walker"""
    try:
        # Check if omarchy-restart-walker is in PATH
        # We also try to use the direct path we discovered earlier
        restart_cmd = shutil.which("omarchy-restart-walker") or "/home/richieee/.local/share/omarchy/bin/omarchy-restart-walker"
        if os.path.exists(restart_cmd):
            subprocess.run([restart_cmd], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        else:
            # Fallback to manual kill if script is missing
            subprocess.run(["killall", "walker", "elephant"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
    except Exception as e:
        logger.debug(f"Failed to restart services: {e}")
        return False


def _map_desktop_category(categories: list, filename: str = "") -> str:
    """Map freedesktop.org categories to CatWalker categories"""
    # Prioritize Browser if WebBrowser is present
    if "WebBrowser" in categories:
        return "Browser"

    for cat in categories:
        if cat in REVERSE_CATEGORY_MAPPING:
            return REVERSE_CATEGORY_MAPPING[cat]
    
    if filename:
        logger.debug(f"No matching internal category for {filename} (Categories: {', '.join(categories)})")
    return None


def cmd_rollback(args):
    """Rollback changes"""
    writer = DesktopFileWriter()

    if args.list:
        backups = writer.list_backups()
        if not backups:
            print("No backups found")
            return 0
        print("\nAvailable backups:")
        for i, backup in enumerate(backups, 1):
            print(f"  {i}. {backup}")
        return 0

    if args.timestamp:
        success = writer.rollback(args.timestamp)
    else:
        backups = writer.list_backups()
        if not backups:
            logger.error("No backups found")
            return 1
        print(f"Rolling back to latest backup: {backups[0]}")
        confirm = input("Proceed? [y/N] ")
        if confirm.lower() != 'y':
            print("Cancelled")
            return 0
        success = writer.rollback()

    if success:
        print("\n✓ Rollback complete")
        print("Restart Walker: killall walker && walker &")
        return 0
    else:
        logger.error("Rollback failed")
        return 1


def cmd_categories(args):
    """List available categories"""
    print("\nAvailable categories:")
    for i, category in enumerate(DEFAULT_CATEGORIES, 1):
        print(f"  {i}. {category}")
    print()


def cmd_sync_db(args):
    """Sync data to PostgreSQL"""
    parser = DesktopFileParser()
    entries = parser.scan_all()
    
    # Map categorized apps
    categorized = {}
    for filename, entry in entries.items():
        cat = _map_desktop_category(entry.categories, filename)
        if cat:
            categorized[filename] = cat

    gen = MenuGenerator()
    usage_data = gen._get_usage_data()

    db = DatabaseSynchronizer()
    if db.init_db():
        if db.sync(entries, usage_data, categorized):
            if not getattr(args, 'quiet', False):
                print("✓ PostgreSQL sync complete")
            return 0
    return 1


def generate_bash_completion():
    """Generate bash completion script for catwalker"""
    completion = '''# bash completion for catwalker
# Source this file: source <(catwalker --generate-completions)

_catwalker_completion() {
    local cur prev words cword
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    words=("${COMP_WORDS[@]}")
    cword=$COMP_CWORD

    local commands="scan categorize menus rollback categories"

    # Show commands if no command yet
    if [[ $COMP_CWORD -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
        return 0
    fi

    # Handle command-specific completions
    case "${words[1]}" in
        scan)
            local scan_opts="-u --uncategorized -c --category -l --limit -h --help"
            COMPREPLY=( $(compgen -W "$scan_opts" -- "$cur") )
            ;;
        categorize)
            local cat_opts="--dry-run -r --recategorize -l --limit -b --batch-size -h --help"
            COMPREPLY=( $(compgen -W "$cat_opts" -- "$cur") )
            ;;
        menus)
            local menu_opts="--dry-run --clean -h --help"
            COMPREPLY=( $(compgen -W "$menu_opts" -- "$cur") )
            ;;
        rollback)
            local rollback_opts="-l --list -t --timestamp -h --help"
            COMPREPLY=( $(compgen -W "$rollback_opts" -- "$cur") )
            ;;
        categories)
            COMPREPLY=( $(compgen -W "-h --help" -- "$cur") )
            ;;
    esac

    return 0
}

complete -o bashdefault -o default -o nospace -F _catwalker_completion catwalker
'''
    return completion


def main():
    parser = argparse.ArgumentParser(
        description='CatWalker - Automatic application categorization using LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
        epilog="""
Examples:
  %(prog)s scan                          # List all applications
  %(prog)s scan --uncategorized          # List uncategorized apps
  %(prog)s categorize                    # Categorize applications
  %(prog)s categorize --dry-run          # Preview changes
  %(prog)s categorize --limit 10         # Test with 10 apps
  %(prog)s menus                         # Generate Walker menu files
  %(prog)s menus --dry-run               # Preview menu generation
  %(prog)s menus --clean                 # Remove generated menus
  %(prog)s rollback                      # Rollback last changes
        """
    )

    # Handle --generate-completions before subparsers
    parser.add_argument('--generate-completions', action='store_true', help='Generate bash completion script')
    if '--generate-completions' in sys.argv:
        print(generate_bash_completion())
        return 0

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Scan
    scan_parser = subparsers.add_parser('scan', help='Scan and list applications')
    scan_parser.add_argument('--uncategorized', '-u', action='store_true')
    scan_parser.add_argument('--category', '-c', type=str)
    scan_parser.add_argument('--limit', '-l', type=int)

    # Categorize
    cat_parser = subparsers.add_parser('categorize', help='Categorize applications via LLM')
    cat_parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying')
    cat_parser.add_argument('--recategorize', '-r', action='store_true')
    cat_parser.add_argument('--limit', '-l', type=int)
    cat_parser.add_argument('--batch-size', '-b', type=int, default=30)

    # Menus
    menu_parser = subparsers.add_parser('menus', help='Generate Elephant menu files for Walker')
    menu_parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    menu_parser.add_argument('--clean', action='store_true', help='Remove generated menu files')
    menu_parser.add_argument('--quiet', '-q', action='store_true', help='Minimal output')

    # Rollback
    rollback_parser = subparsers.add_parser('rollback', help='Rollback changes')
    rollback_parser.add_argument('--list', '-l', action='store_true')
    rollback_parser.add_argument('--timestamp', '-t', type=str)

    # Categories
    subparsers.add_parser('categories', help='List available categories')

    # Sync DB
    sync_parser = subparsers.add_parser('sync-db', help='Sync data to PostgreSQL')
    sync_parser.add_argument('--quiet', '-q', action='store_true', help='Minimal output')

    # Add help manually to avoid conflict with --generate-completions
    parser.add_argument('-h', '--help', action='help', help='Show this help message')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        'scan': cmd_scan,
        'categorize': cmd_categorize,
        'menus': cmd_menus,
        'rollback': cmd_rollback,
        'categories': cmd_categories,
        'sync-db': cmd_sync_db,
    }

    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
