import os
import re
from pathlib import Path

USER_APPS_DIR = Path.home() / ".local/share/applications"

standard_keys = [
    'Name', 'Exec', 'Icon', 'Type', 'Comment', 'GenericName',
    'Categories', 'Terminal', 'NoDisplay', 'Keywords',
    'StartupNotify', 'StartupWMClass', 'MimeType', 'Path',
    'Actions', 'OnlyShowIn', 'NotShowIn', 'Hidden', 'TryExec'
]

def fix_file(filepath: Path):
    try:
        content = filepath.read_text(encoding='utf-8')
        new_content = content
        for key in standard_keys:
            # Replace lowercase key at start of line
            #(?im) for multiline and case-insensitive
            new_content = re.sub(
                f'(?im)^{key}=',
                f'{key}=',
                new_content
            )
        
        if new_content != content:
            filepath.write_text(new_content, encoding='utf-8')
            return True
        return False
    except Exception as e:
        print(f"Error fixing {filepath.name}: {e}")
        return False

def main():
    if not USER_APPS_DIR.exists():
        print(f"Directory not found: {USER_APPS_DIR}")
        return

    fixed = 0
    total = 0
    for filepath in USER_APPS_DIR.glob("*.desktop"):
        total += 1
        if fix_file(filepath):
            fixed += 1
    
    print(f"Fixed {fixed} / {total} files")

if __name__ == "__main__":
    main()
