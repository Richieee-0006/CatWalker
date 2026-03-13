#!/usr/bin/env python3
"""
CatWalker Menu Generator
Generates Elephant/Walker menu files from categorized .desktop entries
"""

import logging
import re
from pathlib import Path
from typing import Dict, List
from parser import DesktopEntry

logger = logging.getLogger(__name__)

MENUS_DIR = Path.home() / ".config/elephant/menus"

CATEGORY_ICONS = {
    "Development": "applications-development",
    "System": "applications-system",
    "Media": "applications-multimedia",
    "Office": "applications-office",
    "Games": "applications-games",
    "Internet": "applications-internet",
    "Graphics": "applications-graphics",
    "Utility": "applications-utilities",
    "Settings": "preferences-system",
    "Education": "applications-science",
    "Browser": "applications-internet",
}

MAIN_MENU_NAME = "catwalker_apps"


class MenuGenerator:
    def __init__(self):
        MENUS_DIR.mkdir(parents=True, exist_ok=True)

    def _sanitize_name(self, name: str) -> str:
        return "apps_" + name.lower().replace(" ", "_")

    def _escape_toml(self, text: str) -> str:
        return text.replace('"', '\\"').replace('\n', ' ').encode('ascii', errors='replace').decode('ascii')

    def _get_exec(self, entry: DesktopEntry) -> str:
        exec_cmd = entry.exec_cmd
        for code in ['%u', '%U', '%f', '%F', '%d', '%D', '%n', '%N', '%i', '%c', '%k', '%v', '%m']:
            exec_cmd = exec_cmd.replace(code, '')
        return exec_cmd.strip()

    # Desktop categories to skip in menus (plugins, not standalone apps)
    SKIP_DESKTOP_CATEGORIES = {'X-LSP-Plugins'}

    def _should_skip(self, entry: DesktopEntry) -> bool:
        return any(c in self.SKIP_DESKTOP_CATEGORIES for c in entry.categories)

    def generate(
        self,
        categorized: Dict[str, str],
        entries: Dict[str, DesktopEntry],
        dry_run: bool = False
    ) -> bool:
        by_category: Dict[str, List[DesktopEntry]] = {}
        skipped = 0
        for filename, category in categorized.items():
            if filename not in entries:
                continue
            entry = entries[filename]
            if self._should_skip(entry):
                skipped += 1
                continue
            by_category.setdefault(category, []).append(entry)
        if skipped:
            logger.info(f"Skipped {skipped} plugin/non-standalone entries")

        for cat in by_category:
            by_category[cat].sort(key=lambda e: e.name.lower())

        if dry_run:
            print("\n[DRY RUN] Would generate these menu files:")
            print(f"  {MENUS_DIR}/{MAIN_MENU_NAME}.toml  (main categories menu)")
            for cat, apps in sorted(by_category.items()):
                menu_name = self._sanitize_name(cat)
                print(f"  {MENUS_DIR}/{menu_name}.toml  ({len(apps)} apps)")
            return True

        self._write_main_menu(list(by_category.keys()))
        for category, app_entries in by_category.items():
            self._write_category_menu(category, app_entries)

        self.update_walker_config()

        logger.info(f"✓ Generated {len(by_category) + 1} menu files in {MENUS_DIR}")
        return True

    def update_walker_config(self) -> bool:
        """Add [providers] empty = ["menus:catwalker_apps"] to Walker config if missing"""
        from config import WALKER_CONFIG_PATH
        
        if not WALKER_CONFIG_PATH.exists():
            logger.warning(f"Walker config not found at {WALKER_CONFIG_PATH}")
            return False

        try:
            content = WALKER_CONFIG_PATH.read_text(encoding='utf-8')
            new_content = content

            provider_match = re.search(r'^\[providers\]', new_content, re.MULTILINE)
            
            if provider_match:
                # Find the next section or end of file
                next_section = re.search(r'^\[', new_content[provider_match.end():], re.MULTILINE)
                section_end = (provider_match.end() + next_section.start()) if next_section else len(new_content)
                section_content = new_content[provider_match.start():section_end]
                
                empty_match = re.search(r'^empty\s*=\s*\[(.*?)\]', section_content, re.MULTILINE)
                if empty_match:
                    items_str = empty_match.group(1).strip()
                    # Parse current items
                    items = []
                    for i in items_str.split(','):
                        i = i.strip().strip('"').strip("'")
                        if i:
                            items.append(i)
                            
                    if f"menus:{MAIN_MENU_NAME}" not in items:
                        items.append(f"menus:{MAIN_MENU_NAME}")
                        new_items_str = ", ".join(f'"{i}"' for i in items)
                        new_empty_line = f'empty = [{new_items_str}]'
                        
                        # Replace only within the section content
                        updated_section = section_content.replace(empty_match.group(0), new_empty_line)
                        new_content = new_content[:provider_match.start()] + updated_section + new_content[section_end:]
                else:
                    # Add empty line to the section after [providers]
                    new_empty_line = f'\nempty = ["menus:{MAIN_MENU_NAME}"]'
                    # Insert after [providers] line
                    insert_pos = provider_match.end()
                    new_content = new_content[:insert_pos] + new_empty_line + new_content[insert_pos:]
            else:
                # Add [providers] section at the end
                if not new_content.endswith('\n'):
                    new_content += '\n'
                new_content += f'\n[providers]\nempty = ["menus:{MAIN_MENU_NAME}"]\n'

            if new_content != content:
                WALKER_CONFIG_PATH.write_text(new_content, encoding='utf-8')
                logger.info(f"✓ Updated Walker config: {WALKER_CONFIG_PATH}")
                return True
            else:
                logger.info("Walker config already contains menus:catwalker_apps in empty providers")
                return True

        except Exception as e:
            logger.error(f"Failed to update Walker config: {e}")
            return False

    def _write_main_menu(self, categories: List[str]):
        from config import DEFAULT_CATEGORIES
        
        lines = [
            f'name = "{MAIN_MENU_NAME}"',
            'name_pretty = "Apps"',
            'icon = "applications-other"',
            'search_name = true',
            'fixed_order = true',
            '',
        ]

        # Use sort order from config.py
        sorted_categories = sorted(
            categories,
            key=lambda c: DEFAULT_CATEGORIES.index(c) if c in DEFAULT_CATEGORIES else len(DEFAULT_CATEGORIES)
        )

        for category in sorted_categories:
            menu_name = self._sanitize_name(category)
            icon = CATEGORY_ICONS.get(category, "applications-other")
            
            lines += [
                '[[entries]]',
                f'text = "{category}"',
                f'icon = "{icon}"',
                f'submenu = "{menu_name}"',
                '',
            ]

        path = MENUS_DIR / f"{MAIN_MENU_NAME}.toml"
        path.write_text('\n'.join(lines), encoding='utf-8')
        logger.info(f"  Written: {path.name}")

    def _write_category_menu(self, category: str, app_entries: List[DesktopEntry]):
        menu_name = self._sanitize_name(category)
        icon = CATEGORY_ICONS.get(category, "applications-other")

        lines = [
            f'name = "{menu_name}"',
            f'name_pretty = "{category}"',
            f'icon = "{icon}"',
            f'parent = "{MAIN_MENU_NAME}"',   # <-- Escape vrátí do hlavního menu
            'search_name = true',
            'history = true',
            '',
        ]

        for entry in app_entries:
            exec_cmd = self._get_exec(entry)
            if not exec_cmd:
                continue
            
            exec_cmd = self._escape_toml(exec_cmd)
            name = self._escape_toml(entry.name)
            icon_name = self._escape_toml(entry.icon) if entry.icon else "application-x-executable"
            comment = self._escape_toml(entry.comment) if entry.comment else ""
            keywords = []
            if entry.generic_name:
                keywords.append(self._escape_toml(entry.generic_name))

            lines += ['[[entries]]', f'text = "{name}"']

            if comment:
                lines.append(f'subtext = "{comment}"')

            if keywords:
                kw_str = ', '.join(f'"{k}"' for k in keywords)
                lines.append(f'keywords = [{kw_str}]')

            lines += [
                f'icon = "{icon_name}"',
                f'actions = {{ launch = "{exec_cmd}" }}',
                '',
            ]

        path = MENUS_DIR / f"{menu_name}.toml"
        path.write_text('\n'.join(lines), encoding='utf-8')
        logger.info(f"  Written: {path.name} ({len(app_entries)} apps)")

    def cleanup(self):
        removed = 0
        for f in MENUS_DIR.glob("catwalker_*.toml"):
            f.unlink()
            removed += 1
        for f in MENUS_DIR.glob("apps_*.toml"):
            f.unlink()
            removed += 1
        logger.info(f"Removed {removed} menu files")
