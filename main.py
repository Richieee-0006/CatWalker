#!/usr/bin/env python3
"""
CatWalker - Automatic application categorization for Walker using LLM
"""

import sys
import argparse
import logging
from typing import Optional

from parser import DesktopFileParser
from categorizer import AppCategorizer, GEMINI_AVAILABLE
from writer import DesktopFileWriter
from config import GEMINI_API_KEY, DEFAULT_CATEGORIES

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

    # Display entries
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
        logger.error(
            "google-generativeai not installed. "
            "Install with: pip install google-generativeai"
        )
        return 1

    if not GEMINI_API_KEY:
        logger.error(
            "GEMINI_API_KEY not set. "
            "Set it with: export GEMINI_API_KEY='your-api-key'"
        )
        return 1

    # Parse applications
    parser = DesktopFileParser()
    entries = parser.scan_all()

    # Filter entries to categorize
    if args.uncategorized:
        entries = parser.get_uncategorized()
        logger.info(f"Categorizing {len(entries)} uncategorized applications")
    elif args.recategorize:
        logger.info(f"Re-categorizing all {len(entries)} applications")
    else:
        entries = parser.get_uncategorized()
        logger.info(f"Categorizing {len(entries)} uncategorized applications")

    if not entries:
        logger.info("No applications to categorize")
        return 0

    # Limit for testing
    if args.limit:
        entries = dict(list(entries.items())[:args.limit])
        logger.info(f"Limited to {args.limit} applications for testing")

    # Categorize using LLM
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
        print(f"" {entry.name}")
        print(f"  {old_cats} ’ {category}")

    # Apply changes
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

    # Summary
    success_count = sum(1 for v in results.values() if v)
    print(f"\n{'=' * 70}")
    print(f"Complete: {success_count}/{len(results)} files processed")
    if args.apply:
        print(f"Backup saved: {writer.backup_timestamp}")
        print("\nRestart Walker to see changes:")
        print("  killall walker && walker &")
    print(f"{'=' * 70}")

    return 0


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
        # Use latest
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
        print("\n Rollback complete")
        print("Restart Walker to see changes:")
        print("  killall walker && walker &")
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


def main():
    parser = argparse.ArgumentParser(
        description='CatWalker - Automatic application categorization using LLM',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s scan                          # List all applications
  %(prog)s scan --uncategorized          # List uncategorized apps
  %(prog)s categorize --dry-run          # Preview categorization
  %(prog)s categorize --apply            # Apply categorization
  %(prog)s categorize --limit 10         # Test with 10 apps
  %(prog)s rollback                      # Rollback to latest backup
  %(prog)s rollback --list               # List available backups

Setup:
  1. Get Gemini API key: https://aistudio.google.com/app/apikey
  2. Export key: export GEMINI_API_KEY='your-key'
  3. Install deps: pip install google-generativeai
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Scan and list applications')
    scan_parser.add_argument(
        '--uncategorized', '-u',
        action='store_true',
        help='Show only uncategorized applications'
    )
    scan_parser.add_argument(
        '--category', '-c',
        type=str,
        help='Filter by category'
    )
    scan_parser.add_argument(
        '--limit', '-l',
        type=int,
        help='Limit number of results'
    )

    # Categorize command
    cat_parser = subparsers.add_parser('categorize', help='Categorize applications')
    cat_parser.add_argument(
        '--apply', '-a',
        action='store_true',
        help='Apply changes (default is dry-run)'
    )
    cat_parser.add_argument(
        '--uncategorized', '-u',
        action='store_true',
        help='Categorize only uncategorized apps'
    )
    cat_parser.add_argument(
        '--recategorize', '-r',
        action='store_true',
        help='Re-categorize all applications'
    )
    cat_parser.add_argument(
        '--limit', '-l',
        type=int,
        help='Limit number of apps (for testing)'
    )
    cat_parser.add_argument(
        '--batch-size', '-b',
        type=int,
        default=50,
        help='Batch size for API calls (default: 50)'
    )

    # Rollback command
    rollback_parser = subparsers.add_parser('rollback', help='Rollback changes')
    rollback_parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List available backups'
    )
    rollback_parser.add_argument(
        '--timestamp', '-t',
        type=str,
        help='Backup timestamp to restore'
    )

    # Categories command
    subparsers.add_parser('categories', help='List available categories')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # Route to command handlers
    commands = {
        'scan': cmd_scan,
        'categorize': cmd_categorize,
        'rollback': cmd_rollback,
        'categories': cmd_categories,
    }

    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
