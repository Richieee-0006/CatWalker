#!/usr/bin/env python3
"""
CatWalker - Automatic application categorization for Walker using LLM
"""

import argparse
import logging
import sys

from categorizer import AppCategorizer
from categorizer import GEMINI_AVAILABLE
from config import DEFAULT_CATEGORIES
from config import GEMINI_API_KEY
from config import REVERSE_CATEGORY_MAPPING
from config import WALKER_MENUS_DIR
from menu_generator import MenuGenerator
from parser import DesktopFileParser
from writer import DesktopFileWriter

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
    if not GEMINI_AVAILABLE:
        logger.error("google-genai not installed. Install with: pip install google-genai")
        return 1

    if not GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY not set. Set it with: export GEMINI_API_KEY='your-api-key'")
        return 1

    parser = DesktopFileParser()
    entries = parser.scan_all()

    if args.recategorize:
        logger.info(f"Re-categorizing all {len(entries)} applications")
    else:
        entries = parser.get_uncategorized()
        logger.info(f"Categorizing {len(entries)} uncategorized applications")

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
    writer = DesktopFileWriter(dry_run=not args.apply)

    print(f"\n{'=' * 70}")
    if args.apply:
        print("Applying changes...")
        confirm = input("\nProceed? [y/N] ")
        if confirm.lower() != 'y':
            print("Cancelled")
            return 0
    else:
        print("DRY RUN - No changes will be made")
        print("Use --apply to actually modify files")

    print(f"{'=' * 70}\n")

    results = writer.apply_categorization(entries, categorization)
    success_count = sum(1 for v in results.values() if v)

    print(f"\n{'=' * 70}")
    print(f"Complete: {success_count}/{len(results)} files processed")
    if args.apply:
        print(f"Backup saved: {writer.backup_timestamp}")
        print("\nRestart Walker to see changes:")
        print("  killall walker && walker &")
    print(f"{'=' * 70}")

    return 0


def cmd_menus(args):
    """Generate Elephant menu files from categorized apps"""
    if args.clean:
        gen = MenuGenerator()
        gen.cleanup()
        print("✓ Removed CatWalker menu files")
        print("Restart Walker: killall walker && walker &")
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
    
    if uncategorized_count > 0:
	    logger.warning(f"{uncategorized_count} applications are uncategorized and will be missing from menus.")
	    print(f"Suggestion: Run './catwalker categorize --apply' to include them.")

    print(f"\nFound {len(categorized)} categorized applications")

    gen = MenuGenerator()

    if args.dry_run:
        gen.generate(categorized, entries, dry_run=True)
        print("\nUse without --dry-run to actually generate files")
        return 0
    
    if gen.generate(categorized, entries):
	    print(f"\n{'=' * 70}")
	    print(f"✓ Menu files generated in {WALKER_MENUS_DIR}")
	    print("✓ Walker configuration updated")
	    print("\nRestart Walker to see changes:")
	    print("  killall walker && walker &")
	    print(f"{'=' * 70}")
	    return 0
    return 1


def _map_desktop_category(categories: list, filename: str = "") -> str:
    """Map freedesktop.org categories to CatWalker categories"""
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
            local cat_opts="-a --apply -r --recategorize -l --limit -b --batch-size -h --help"
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
  %(prog)s categorize                    # Categorize (dry-run)
  %(prog)s categorize --apply            # Apply to .desktop files
  %(prog)s categorize --limit 10         # Test with 10 apps
  %(prog)s menus                         # Generate Walker menu files
  %(prog)s menus --dry-run               # Preview menu generation
  %(prog)s menus --clean                 # Remove generated menus
  %(prog)s rollback                      # Rollback last changes
        """
    )

    # Handle --generate-completions before subparsers
    parser.add_argument('--generate-completions', action = 'store_true', help = 'Generate bash completion script')
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
    cat_parser.add_argument('--apply', '-a', action='store_true', help='Apply changes')
    cat_parser.add_argument('--recategorize', '-r', action='store_true')
    cat_parser.add_argument('--limit', '-l', type=int)
    cat_parser.add_argument('--batch-size', '-b', type=int, default=50)

    # Menus
    menu_parser = subparsers.add_parser('menus', help='Generate Elephant menu files for Walker')
    menu_parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
    menu_parser.add_argument('--clean', action='store_true', help='Remove generated menu files')

    # Rollback
    rollback_parser = subparsers.add_parser('rollback', help='Rollback changes')
    rollback_parser.add_argument('--list', '-l', action='store_true')
    rollback_parser.add_argument('--timestamp', '-t', type=str)

    # Categories
    subparsers.add_parser('categories', help='List available categories')

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
    }

    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
