#!/usr/bin/env python3
import logging
import re
from pathlib import Path

from config import USER_APPS_DIR

logging.basicConfig(level = logging.INFO, format = '%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

def fix_file(filepath: Path) -> bool:
    """Standardize .desktop file keys to be case-sensitive and correctly capitalized."""
    try:
        content = filepath.read_text(encoding = 'utf-8')
        
        # Standard keys from freedesktop.org to strictly capitalize
        standard_keys = [
            'Name', 'Exec', 'Icon', 'Type', 'Comment', 'GenericName',
            'Categories', 'Terminal', 'NoDisplay', 'Keywords',
            'StartupNotify', 'StartupWMClass', 'MimeType', 'Path',
            'Actions', 'OnlyShowIn', 'NotShowIn', 'Hidden', 'TryExec'
        ]
        
        new_content = content
        
        # Note: Removing the 'i' flag for strictly matching the standard would be counter-productive
        # for a 'fix' script whose job is to correct lowercase keys.
        # We will iterate to ensure exact replacement of the key part only.
        for key in standard_keys:
            # Case-sensitive check first to avoid unnecessary changes
            new_content = re.sub(
                f'^{key}=',
                f'{key}=',
                new_content,
                flags = re.MULTILINE
            )
            # Then fix the ones that are definitely wrong (lowercase)
            new_content = re.sub(
                f'^{key.lower()}=',
                f'{key}=',
                new_content,
                flags = re.MULTILINE
            )

        if new_content != content:
            filepath.write_text(new_content, encoding='utf-8')
            logger.info(f"✓ Fixed keys in {filepath.name}")
            return True
        return False
    
    except (IOError, UnicodeDecodeError) as e:
        logger.error(f"Error processing {filepath.name}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error fixing {filepath.name}: {e}")
        return False

def main():
    if not USER_APPS_DIR.exists():
        logger.error(f"Directory not found: {USER_APPS_DIR}")
        return

    logger.info(f"Scanning {USER_APPS_DIR} for .desktop files to fix...")
    fixed_count = 0
    total_count = 0
    
    for filepath in USER_APPS_DIR.glob("*.desktop"):
        total_count += 1
        if fix_file(filepath):
            fixed_count += 1
    
    logger.info(f"Done. Processed {total_count} files, fixed {fixed_count}.")

if __name__ == "__main__":
    main()
