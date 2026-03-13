#!/usr/bin/env python3
"""
CatWalker Menu Generator
Generates Elephant/Walker menu files from categorized .desktop entries
"""

import logging
import re
from typing import Dict
from typing import List

from config import DEFAULT_CATEGORIES
from config import WALKER_CONFIG_PATH
from config import WALKER_MENUS_DIR
from parser import DesktopEntry

logger = logging.getLogger(__name__)

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
	    try:
		    WALKER_MENUS_DIR.mkdir(parents = True, exist_ok = True)
	    except Exception as e:
		    logger.error(f"Failed to create menus directory {WALKER_MENUS_DIR}: {e}")
		    raise

    def _sanitize_name(self, name: str) -> str:
        return "apps_" + name.lower().replace(" ", "_")

    def _escape_toml(self, text: str) -> str:
        return text.replace('"', '\\"').replace('\n', ' ').encode('ascii', errors='replace').decode('ascii')

    def _get_exec(self, entry: DesktopEntry) -> str:
        exec_cmd = entry.exec_cmd
        # Remove standard field codes
        for code in ['%u', '%U', '%f', '%F', '%d', '%D', '%n', '%N', '%i', '%c', '%k', '%v', '%m']:
            exec_cmd = exec_cmd.replace(code, '')
        return exec_cmd.strip()

    # Desktop categories to skip in menus (plugins, not standalone apps)
    SKIP_DESKTOP_CATEGORIES = {'X-LSP-Plugins'}

    def _should_skip(self, entry: DesktopEntry) -> bool:
	    if any(c in self.SKIP_DESKTOP_CATEGORIES for c in entry.categories):
		    logger.debug(f"Skipping plugin/non-standalone entry: {entry.filename}")
		    return True
	    return False

    def generate(
        self,
        categorized: Dict[str, str],
        entries: Dict[str, DesktopEntry],
        dry_run: bool = False
    ) -> bool:
        by_category: Dict[str, List[DesktopEntry]] = {}
        skipped_entries = []
        
        for filename, category in categorized.items():
            if filename not in entries:
                continue
            entry = entries[filename]
            if self._should_skip(entry):
	            skipped_entries.append(filename)
                continue
            by_category.setdefault(category, []).append(entry)
        
        if skipped_entries:
	        logger.info(f"Skipped {len(skipped_entries)} plugin/non-standalone entries: {', '.join(skipped_entries[:5])}...")

        for cat in by_category:
            by_category[cat].sort(key=lambda e: e.name.lower())

        if dry_run:
            print("\n[DRY RUN] Would generate these menu files:")
            print(f"  {WALKER_MENUS_DIR}/{MAIN_MENU_NAME}.toml  (main categories menu)")
            for cat, apps in sorted(by_category.items()):
                menu_name = self._sanitize_name(cat)
                print(f"  {WALKER_MENUS_DIR}/{menu_name}.toml  ({len(apps)} apps)")
            return True
        
        success = True
        try:
	        self._write_main_menu(list(by_category.keys()))
	        for category, app_entries in by_category.items():
		        self._write_category_menu(category, app_entries)
	        
	        self.update_walker_config()
	        logger.info(f"✓ Generated {len(by_category) + 1} menu files in {WALKER_MENUS_DIR}")
        except Exception as e:
	        logger.error(f"Failed during menu generation: {e}")
	        success = False
        
        return success
    
    def _update_section_content(self, section_content: str, provider_name: str) -> str:
	    """Update the 'empty' key within the [providers] section content."""
	    empty_match = re.search(r'^empty\s*=\s*\[(.*?)\]', section_content, re.MULTILINE)
	    if empty_match:
		    items_str = empty_match.group(1).strip()
		    items = [i.strip().strip('"').strip("'") for i in items_str.split(',') if i.strip()]
		    
		    if provider_name not in items:
			    items.append(provider_name)
			    new_items_str = ", ".join(f'"{i}"' for i in items)
			    new_empty_line = f'empty = [{new_items_str}]'
			    return section_content.replace(empty_match.group(0), new_empty_line)
	    else:
		    # Add empty line to the existing section
		    return section_content.rstrip() + f'\nempty = ["{provider_name}"]\n'
	    return section_content

    def update_walker_config(self) -> bool:
	    """Safely add [providers] empty = ["menus:catwalker_apps"] to Walker config."""
        if not WALKER_CONFIG_PATH.exists():
            logger.warning(f"Walker config not found at {WALKER_CONFIG_PATH}")
            return False
	    
	    provider_name = f"menus:{MAIN_MENU_NAME}"
        try:
            content = WALKER_CONFIG_PATH.read_text(encoding='utf-8')
            new_content = content

            provider_match = re.search(r'^\[providers\]', new_content, re.MULTILINE)
            
            if provider_match:
	            # Extract section to avoid affecting other parts of the file
                next_section = re.search(r'^\[', new_content[provider_match.end():], re.MULTILINE)
                section_end = (provider_match.end() + next_section.start()) if next_section else len(new_content)
                section_content = new_content[provider_match.start():section_end]
	            
	            updated_section = self._update_section_content(section_content, provider_name)
	            new_content = new_content[:provider_match.start()] + updated_section + new_content[section_end:]
            else:
	            # Add entirely new [providers] section
                if not new_content.endswith('\n'):
                    new_content += '\n'
	            new_content += f'\n[providers]\nempty = ["{provider_name}"]\n'

            if new_content != content:
	            # Validation: ensure we haven't corrupted the file (basic check)
	            if "[providers]" in new_content and provider_name in new_content:
		            WALKER_CONFIG_PATH.write_text(new_content, encoding = 'utf-8')
		            logger.info(f"✓ Updated Walker config: {WALKER_CONFIG_PATH}")
		            return True
            else:
	            logger.info(f"Walker config already contains {provider_name} in empty providers")
                return True

        except Exception as e:
	        logger.error(f"Failed to update Walker config at {WALKER_CONFIG_PATH}: {e}")
            return False
	    return True

    def _write_main_menu(self, categories: List[str]):
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
        
        try:
	        path = WALKER_MENUS_DIR / f"{MAIN_MENU_NAME}.toml"
	        path.write_text('\n'.join(lines), encoding = 'utf-8')
	        logger.info(f"  Written: {path.name}")
        except Exception as e:
	        logger.error(f"Failed to write main menu file: {e}")
	        raise

    def _write_category_menu(self, category: str, app_entries: List[DesktopEntry]):
        menu_name = self._sanitize_name(category)
        icon = CATEGORY_ICONS.get(category, "applications-other")

        lines = [
            f'name = "{menu_name}"',
            f'name_pretty = "{category}"',
            f'icon = "{icon}"',
	        f'parent = "{MAIN_MENU_NAME}"',
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
            
            lines += ['[[entries]]', f'text = "{name}"']
            if comment:
                lines.append(f'subtext = "{comment}"')
            if entry.generic_name:
	            lines.append(f'keywords = ["{self._escape_toml(entry.generic_name)}"]')

            lines += [
                f'icon = "{icon_name}"',
                f'actions = {{ launch = "{exec_cmd}" }}',
                '',
            ]
        
        try:
	        path = WALKER_MENUS_DIR / f"{menu_name}.toml"
	        path.write_text('\n'.join(lines), encoding = 'utf-8')
	        logger.info(f"  Written: {path.name} ({len(app_entries)} apps)")
        except Exception as e:
	        logger.error(f"Failed to write category menu file {menu_name}: {e}")
	        raise

    def cleanup(self):
        removed = 0
        try:
	        for f in WALKER_MENUS_DIR.glob("catwalker_*.toml"):
		        f.unlink()
		        removed += 1
	        for f in WALKER_MENUS_DIR.glob("apps_*.toml"):
		        f.unlink()
		        removed += 1
	        logger.info(f"Removed {removed} menu files")
        except Exception as e:
	        logger.error(f"Cleanup failed: {e}")
