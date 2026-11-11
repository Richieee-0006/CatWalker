# CatWalker 🐱

Automatická kategorizace Linuxových aplikací pro Walker/Elephant pomocí LLM.

## Features

- 🤖 **Inteligentní kategorizace** - Gemma 3 27B přes Google AI REST API
- 📊 **Automatické řazení podle použití** - Automaticky řadí aplikace i kategorie v menu podle historie Walkeru
- 🔒 **Bezpečné** - nikdy nemodifikuje systémové soubory, vše v `~/.local/share/applications/`
- 💾 **Automatický backup** - před každou změnou vytvoří zálohu
- 🔄 **Rollback** - snadné vrácení změn
- 🎯 **Dry-run mode** - preview před aplikací změn
- 📂 **Walker menu generátor** - vytvoří kategorie jako složky v Walkeru
- ⚡ **REST API Integration** - Přímé volání API bez nutnosti instalovat těžký Gemini SDK (vhodné pro Python 3.14+)

## Instalace

### 1. Základní setup

```bash
cd ~/Work
git clone <repo-url> CatWalker
cd CatWalker

# Virtual environment (Arch Linux)
python -m venv .venv

# Závislosti (vyžaduje 'requests', nepotřebuje 'google-generativeai' SDK)
pip install -r requirements.txt

# API klíč (Google AI Studio - free tier)
# https://aistudio.google.com/app/apikey
echo "export GEMINI_API_KEY='your-api-key-here'" >> ~/.bashrc
source ~/.bashrc
```

### 2. System-wide Setup (Optional)

Uděláte `catwalker` dostupný z jakéhokoliv adresáře:

```bash
# Symlink wrapper
ln -s "$(pwd)/catwalker" ~/.local/bin/catwalker

# Ověřte, že ~/.local/bin je v PATH
echo $PATH | grep ".local/bin"
```

### 3. Shell Auto-completion

#### Bash

```bash
# Auto-completion vygenerujete a přidáte do .bashrc:
echo 'source <(catwalker --generate-completions)' >> ~/.bashrc
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
```

### 2. Vygenerovat Walker menus

```bash
# Vygeneruje ~/.config/elephant/menus/catwalker_*.toml
# A automaticky aktualizuje ~/.config/walker/config.toml
catwalker menus

# Preview
catwalker menus --dry-run

# Smazat vygenerované soubory
catwalker menus --clean
```

Restart: `killall walker; sleep 1 && walker &`

## Architektura

```
parser.py          # Parsuje .desktop soubory
categorizer.py     # Volá Google AI REST API (přes requests)
writer.py          # Bezpečně upravuje Categories= (pomocí regex)
menu_generator.py  # Generuje Elephant TOML menu soubory a Walker config
main.py            # CLI interface a command router
config.py          # Centrální konfigurace a cesty
catwalker          # Bash wrapper script
```

## Troubleshooting

### API klíč nefunguje
Zkontrolujte, zda je proměnná `GEMINI_API_KEY` správně nastavena v prostředí: `echo $GEMINI_API_KEY`.

### .desktop soubory mají lowercase klíče
`writer.py` používá regex, který automaticky opravuje kapitalizaci standardních klíčů (např. `categories=` -> `Categories=`).

## License

MIT — richieee @ 2026
