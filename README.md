# CatWalker 🐱

Automatická kategorizace Linuxových aplikací pro Walker/Elephant pomocí LLM.

## Features

- 🤖 **Inteligentní kategorizace** - Gemma 3 27B přes Google AI API
- 🔒 **Bezpečné** - nikdy nemodifikuje systémové soubory, vše v `~/.local/share/applications/`
- 💾 **Automatický backup** - před každou změnou vytvoří zálohu
- 🔄 **Rollback** - snadné vrácení změn
- 🎯 **Dry-run mode** - preview před aplikací změn
- 📂 **Walker menu generátor** - vytvoří kategorie jako složky v Walkeru

## Instalace

### 1. Základní setup

```bash
cd ~/Work
git clone <repo-url> CatWalker
cd CatWalker

# Virtual environment (Arch Linux)
python -m venv .venv

# Závislosti
pip install -r requirements.txt

# API klíč (Google AI Studio - free tier)
# https://aistudio.google.com/app/apikey
echo "export GEMINI_API_KEY='your-api-key-here'" >> ~/.bashrc
source ~/.bashrc
```

### 2. System-wide Setup (Optional)

Uděláte `catwalker` dostupný z jakéhokoliv adresáře:

```bash
# Symlink wrapper (already done if you ran install script)
# ~/.local/bin/catwalker je již vytvořen automaticky

# Ověřte, že ~/.local/bin je v PATH (mělo by být)
echo $PATH | grep ".local/bin"

# Pokud ne, přidejte do ~/.bashrc:
# export PATH="$HOME/.local/bin:$PATH"
```

### 3. Shell Auto-completion

#### Bash

```bash
# Auto-completion se vytvořená automaticky v:
# ~/.local/share/bash-completion/completions/catwalker

# Vyzkoušejte:
catwalker <TAB>  # Mělo by se zobrazit seznam příkazů
catwalker categorize <TAB>  # Mělo by se zobrazit seznam příznaků
```

#### Zsh

Zsh auto-completion je nainstalován v:
```
~/.local/share/zsh/site-functions/_catwalker
```

Ověřte si, že `~/.local/share/zsh/site-functions` je v `$fpath`:

```bash
# Přidejte do ~/.zshrc pokud chybí:
# export fpath=(~/.local/share/zsh/site-functions $fpath)
```

## Použití

Wrapper `catwalker` automaticky aktivuje `.venv`, takže můžete zavolat odkudkoliv:

```bash
catwalker --help          # Nápověda
catwalker categories      # Seznam kategorií
```

### 1. Kategorizovat aplikace

```bash
# Preview (dry-run)
catwalker categorize

# Aplikovat na všechny nekategorizované
catwalker categorize --apply

# Rekategorizovat vše znovu
catwalker categorize --recategorize --apply

# Test na malém vzorku
catwalker categorize --limit 10 --apply
```

### 2. Vygenerovat Walker menus

```bash
# Vygeneruje ~/.config/elephant/menus/catwalker_*.toml
# A automaticky přidá do ~/.config/walker/config.toml: [providers] empty = ["menus:catwalker_apps"]
./catwalker menus

# Preview
./catwalker menus --dry-run

# Smazat vygenerované soubory
./catwalker menus --clean
```

Restart: `systemctl --user restart elephant && killall walker; sleep 1 && walker &`

### 3. Ostatní příkazy

```bash
./catwalker scan                    # Zobraz všechny aplikace
./catwalker scan --uncategorized    # Jen nekategorizované
./catwalker scan --category Network # Filtr podle kategorie
./catwalker rollback                # Vrať poslední změny
./catwalker rollback --list         # Zobraz dostupné zálohy
./catwalker categories              # Zobraz dostupné kategorie
```

## Konfigurace (`config.py`)

```python
MODEL_NAME = "gemma-3-27b-it"   # Gemma 3 - lepší rate limity než Gemini Flash

DEFAULT_CATEGORIES = [
    "Development", "System", "Media", "Office",
    "Games", "Internet", "Graphics", "Utility",
    "Settings", "Education", "Browser",
]
```

## Kategorie

| Kategorie | Aplikace |
|-----------|----------|
| Development | IDE, editory, dev tools |
| System | Terminály, monitoring, správa |
| Media | Audio, video, přehrávače, DAW pluginy |
| Office | Dokumenty, tabulky, prezentace |
| Games | Hry, game launchery |
| Internet | Chat, email, sociální sítě |
| Browser | Webové prohlížeče |
| Graphics | Grafické editory, prohlížeče obrázků |
| Utility | Obecné nástroje |
| Settings | Nastavení systému |
| Education | Vzdělávací aplikace |

## Architektura

```
parser.py          # Parsuje .desktop soubory
categorizer.py     # Volá Google AI API (requests, bez SDK)
writer.py          # Bezpečně upravuje Categories= (regex, ne configparser)
menu_generator.py  # Generuje Elephant TOML menu soubory
main.py            # CLI interface
config.py          # Konfigurace
catwalker          # Wrapper script (.venv + main.py)
```

## Troubleshooting

### Elephant není připojený
```bash
systemctl --user start elephant
systemctl --user status elephant
```

### API klíč nefunguje
```bash
echo $GEMINI_API_KEY   # Zkontroluj že je nastaven
```

### .desktop soubory mají lowercase klíče
Starý problém s configparser — writer.py nyní používá regex a zachovává originální formátování.

## License

MIT — richieee @ 2026
