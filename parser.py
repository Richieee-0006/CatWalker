import configparser
from pathlib import Path
from typing import Dict, List, Optional
import logging

from config import SYSTEM_APPS_DIR, USER_APPS_DIR

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DesktopEntry:
    """Represents a parsed .desktop file"""

    def __init__(self, filename: str, filepath: Path):
        self.filename = filename
        self.filepath = filepath
        self.name: str = ""
        self.comment: str = ""
        self.generic_name: str = ""
        self.categories: List[str] = []
        self.icon: str = ""
        self.exec_cmd: str = ""
        self.no_display: bool = False

    def __repr__(self):
        return f"<DesktopEntry: {self.name} ({self.filename})>"

    def get_context(self) -> str:
        """Get contextual information for LLM"""
        context_parts = [self.name]
        if self.generic_name and self.generic_name != self.name:
            context_parts.append(f"({self.generic_name})")
        if self.comment:
            context_parts.append(f"- {self.comment}")
        return " ".join(context_parts)


class DesktopFileParser:
    """Parser for .desktop files"""

    def __init__(self):
        self.entries: Dict[str, DesktopEntry] = {}

    def parse_file(self, filepath: Path) -> Optional[DesktopEntry]:
        """Parse a single .desktop file"""
        try:
            config = configparser.ConfigParser(strict=False, interpolation=None)
            config.read(filepath, encoding='utf-8')

            if 'Desktop Entry' not in config:
                logger.warning(f"No [Desktop Entry] section in {filepath}")
                return None

            section = config['Desktop Entry']

            # Skip if NoDisplay=true
            if section.get('NoDisplay', '').lower() == 'true':
                return None

            # Skip if Type is not Application
            if section.get('Type', '').lower() != 'application':
                return None

            entry = DesktopEntry(filepath.name, filepath)
            entry.name = section.get('Name', filepath.stem)
            entry.comment = section.get('Comment', '')
            entry.generic_name = section.get('GenericName', '')
            entry.icon = section.get('Icon', '')
            entry.exec_cmd = section.get('Exec', '')

            # Parse categories
            categories_str = section.get('Categories', '')
            if categories_str:
                entry.categories = [c.strip() for c in categories_str.split(';') if c.strip()]

            return entry

        except Exception as e:
            logger.error(f"Error parsing {filepath}: {e}")
            return None

    def scan_directories(self, directories: List[Path]) -> Dict[str, DesktopEntry]:
        """Scan directories for .desktop files"""
        entries = {}

        for directory in directories:
            if not directory.exists():
                logger.warning(f"Directory not found: {directory}")
                continue

            logger.info(f"Scanning {directory}")

            for filepath in directory.glob("*.desktop"):
                entry = self.parse_file(filepath)
                if entry:
                    # User apps override system apps
                    entries[filepath.name] = entry

        logger.info(f"Found {len(entries)} applications")
        return entries

    def scan_all(self) -> Dict[str, DesktopEntry]:
        """Scan both system and user directories"""
        # Scan system first, then user (user overrides system)
        directories = [SYSTEM_APPS_DIR, USER_APPS_DIR]
        self.entries = self.scan_directories(directories)
        return self.entries

    def get_uncategorized(self) -> Dict[str, DesktopEntry]:
        """Get applications without categories"""
        return {
            filename: entry
            for filename, entry in self.entries.items()
            if not entry.categories
        }

    def get_by_category(self, category: str) -> Dict[str, DesktopEntry]:
        """Get applications by category"""
        return {
            filename: entry
            for filename, entry in self.entries.items()
            if category in entry.categories
        }

    def get_system_only(self) -> Dict[str, DesktopEntry]:
        """Get applications that are in system directory but NOT in user directory"""
        return {
            filename: entry
            for filename, entry in self.entries.items()
            if not (USER_APPS_DIR / filename).exists()
        }


def main():
    """Test parser"""
    parser = DesktopFileParser()
    entries = parser.scan_all()

    print(f"\nTotal applications: {len(entries)}")
    print(f"Uncategorized: {len(parser.get_uncategorized())}")

    print("\n--- Sample Applications ---")
    for filename, entry in list(entries.items())[:5]:
        print(f"\n{filename}:")
        print(f"  Name: {entry.name}")
        print(f"  Comment: {entry.comment}")
        print(f"  Categories: {', '.join(entry.categories) if entry.categories else 'None'}")


if __name__ == "__main__":
    main()
