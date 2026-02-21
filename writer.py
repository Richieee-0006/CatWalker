import shutil
import logging
from pathlib import Path
from typing import Dict, List
from datetime import datetime
import configparser

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
        """Get backup path for a file"""
        backup_subdir = BACKUP_DIR / self.backup_timestamp
        backup_subdir.mkdir(parents=True, exist_ok=True)
        return backup_subdir / filename

    def _backup_file(self, filepath: Path) -> bool:
        """Create backup of a file"""
        try:
            backup_path = self._get_backup_path(filepath.name)
            shutil.copy2(filepath, backup_path)
            logger.debug(f"Backed up {filepath.name} to {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to backup {filepath}: {e}")
            return False

    def _ensure_user_copy(self, entry: DesktopEntry) -> Path:
        """
        Ensure .desktop file exists in user directory
        Copy from system if needed
        """
        user_file = USER_APPS_DIR / entry.filename

        # If already in user dir, just return it
        if user_file.exists():
            return user_file

        # Copy from system to user directory
        if entry.filepath.exists():
            logger.info(f"Copying {entry.filename} to user directory")
            shutil.copy2(entry.filepath, user_file)
            return user_file
        else:
            raise FileNotFoundError(f"Source file not found: {entry.filepath}")

    def _update_categories(self, filepath: Path, categories: List[str]) -> bool:
        """
        Update Categories field in .desktop file
        """
        try:
            # Read file
            config = configparser.ConfigParser(strict=False, interpolation=None)
            config.read(filepath, encoding='utf-8')

            if 'Desktop Entry' not in config:
                logger.error(f"No [Desktop Entry] section in {filepath}")
                return False

            # Update categories
            categories_str = ";".join(categories) + ";"
            config['Desktop Entry']['Categories'] = categories_str

            # Write back
            with open(filepath, 'w', encoding='utf-8') as f:
                config.write(f, space_around_delimiters=False)

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
        """
        Apply categorization to desktop files

        Args:
            entries: Dictionary of desktop entries
            categorization: Dictionary mapping filename to category

        Returns:
            Dictionary of filename -> success status
        """
        results = {}

        for filename, category in categorization.items():
            if filename not in entries:
                logger.warning(f"Entry not found: {filename}")
                results[filename] = False
                continue

            entry = entries[filename]

            try:
                # Map category to freedesktop.org standard
                desktop_category = CATEGORY_MAPPINGS.get(category, category)

                logger.info(f"Processing {entry.name} ({filename}) -> {category}")

                if self.dry_run:
                    logger.info(f"  [DRY RUN] Would set categories to: {desktop_category}")
                    results[filename] = True
                    continue

                # Ensure file is in user directory
                user_file = self._ensure_user_copy(entry)

                # Backup existing file
                if user_file.exists():
                    self._backup_file(user_file)

                # Update categories
                # Keep some existing categories that make sense
                new_categories = [desktop_category]

                # Preserve important existing categories
                preserve_cats = ['Settings', 'Qt', 'GTK', 'GNOME', 'KDE']
                for cat in entry.categories:
                    if cat in preserve_cats and cat not in new_categories:
                        new_categories.append(cat)

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

        # Summary
        success_count = sum(1 for v in results.values() if v)
        logger.info(
            f"\nCompleted: {success_count}/{len(results)} files "
            f"{'(DRY RUN)' if self.dry_run else 'modified'}"
        )

        return results

    def rollback(self, backup_timestamp: str = None) -> bool:
        """
        Rollback changes from a backup

        Args:
            backup_timestamp: Timestamp of backup to restore (default: latest)
        """
        try:
            # Find backup directory
            if backup_timestamp:
                backup_dir = BACKUP_DIR / backup_timestamp
            else:
                # Use latest backup
                backups = sorted(BACKUP_DIR.glob("*"), reverse=True)
                if not backups:
                    logger.error("No backups found")
                    return False
                backup_dir = backups[0]

            if not backup_dir.exists():
                logger.error(f"Backup not found: {backup_dir}")
                return False

            logger.info(f"Rolling back from {backup_dir.name}")

            # Restore files
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
        """List available backups"""
        backups = sorted(BACKUP_DIR.glob("*"), reverse=True)
        return [b.name for b in backups if b.is_dir()]


def main():
    """Test writer"""
    print("Writer module - use via main.py")


if __name__ == "__main__":
    main()
