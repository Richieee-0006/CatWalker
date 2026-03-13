import shutil
import logging
import re
from pathlib import Path
from typing import Dict, List
from datetime import datetime

from config import (
    SYSTEM_APPS_DIR,
    USER_APPS_DIR,
    BACKUP_DIR,
    CATEGORY_MAPPINGS
)
from parser import DesktopEntry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DesktopFileWriter:
    """Safely writes .desktop files to user directory"""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.modified_files: List[str] = []

    def _get_backup_path(self, filename: str) -> Path:
        backup_subdir = BACKUP_DIR / self.backup_timestamp
        backup_subdir.mkdir(parents=True, exist_ok=True)
        return backup_subdir / filename

    def _backup_file(self, filepath: Path) -> bool:
        try:
            backup_path = self._get_backup_path(filepath.name)
            shutil.copy2(filepath, backup_path)
            logger.debug(f"Backed up {filepath.name} to {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to backup {filepath}: {e}")
            return False

    def _ensure_user_copy(self, entry: DesktopEntry) -> Path:
        user_file = USER_APPS_DIR / entry.filename
        if user_file.exists():
            return user_file
        if entry.filepath.exists():
            logger.info(f"Copying {entry.filename} to user directory")
            shutil.copy2(entry.filepath, user_file)
            return user_file
        else:
            raise FileNotFoundError(f"Source file not found: {entry.filepath}")

    def _update_categories(self, filepath: Path, categories: List[str]) -> bool:
        """
        Update Categories= field using direct text manipulation
        to avoid configparser lowercasing all keys.
        Also fixes capitalization of standard keys.
        """
        try:
            content = filepath.read_text(encoding='utf-8')
            
            # Standard keys to capitalize
            standard_keys = [
                'Name', 'Exec', 'Icon', 'Type', 'Comment', 'GenericName',
                'Categories', 'Terminal', 'NoDisplay', 'Keywords',
                'StartupNotify', 'StartupWMClass', 'MimeType', 'Path',
                'Actions', 'OnlyShowIn', 'NotShowIn', 'Hidden', 'TryExec'
            ]
            
            new_content = content
            for key in standard_keys:
                # Replace lowercase key at start of line
                new_content = re.sub(
                    f'(?im)^{key}=',
                    f'{key}=',
                    new_content
                )

            categories_str = ";".join(categories) + ";"

            # Replace existing Categories= line
            new_content, count = re.subn(
                r'(?im)^Categories=.*$',
                f'Categories={categories_str}',
                new_content
            )

            # If no Categories= line existed, add it after [Desktop Entry]
            if count == 0:
                new_content = re.sub(
                    r'(\[Desktop Entry\])',
                    f'\\1\nCategories={categories_str}',
                    new_content
                )

            filepath.write_text(new_content, encoding='utf-8')
            logger.debug(f"Updated categories in {filepath.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to update {filepath}: {e}")
            return False

    def apply_categorization(
        self,
        entries: Dict[str, DesktopEntry],
        categorization: Dict[str, str]
    ) -> Dict[str, bool]:
        results = {}

        for filename, category in categorization.items():
            if filename not in entries:
                logger.warning(f"Entry not found: {filename}")
                results[filename] = False
                continue

            entry = entries[filename]

            try:
                desktop_category = CATEGORY_MAPPINGS.get(category, category)
                logger.info(f"Processing {entry.name} ({filename}) -> {category}")

                if self.dry_run:
                    logger.info(f"  [DRY RUN] Would set categories to: {desktop_category}")
                    results[filename] = True
                    continue

                user_file = self._ensure_user_copy(entry)

                if user_file.exists():
                    self._backup_file(user_file)

                # Keep all existing categories, just add the new one if not present
                new_categories = list(entry.categories)
                if desktop_category not in new_categories:
                    new_categories.insert(0, desktop_category)

                success = self._update_categories(user_file, new_categories)

                if success:
                    self.modified_files.append(filename)
                    logger.info(f"  ✓ Updated {filename}")
                else:
                    logger.error(f"  ✗ Failed to update {filename}")

                results[filename] = success

            except Exception as e:
                logger.error(f"Error processing {filename}: {e}")
                results[filename] = False

        success_count = sum(1 for v in results.values() if v)
        logger.info(
            f"\nCompleted: {success_count}/{len(results)} files "
            f"{'(DRY RUN)' if self.dry_run else 'modified'}"
        )

        return results

    def rollback(self, backup_timestamp: str = None) -> bool:
        try:
            if backup_timestamp:
                backup_dir = BACKUP_DIR / backup_timestamp
            else:
                backups = sorted(BACKUP_DIR.glob("*"), reverse=True)
                if not backups:
                    logger.error("No backups found")
                    return False
                backup_dir = backups[0]

            if not backup_dir.exists():
                logger.error(f"Backup not found: {backup_dir}")
                return False

            logger.info(f"Rolling back from {backup_dir.name}")
            restored = 0
            for backup_file in backup_dir.glob("*.desktop"):
                target_file = USER_APPS_DIR / backup_file.name
                shutil.copy2(backup_file, target_file)
                logger.info(f"  Restored {backup_file.name}")
                restored += 1

            logger.info(f"✓ Restored {restored} files")
            return True

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False

    def list_backups(self) -> List[str]:
        backups = sorted(BACKUP_DIR.glob("*"), reverse=True)
        return [b.name for b in backups if b.is_dir()]
