# CatWalker

Automatická kategorizace linuxových aplikací pro launchery Walker a Elephant pomocí LLM.

## Funkce

- Kategorizace přes Gemma 3 27B (Google AI REST API přes `requests`, bez závislosti na `google-generativeai` SDK).
- Řazení aplikací i kategorií v menu podle historie používání ve Walkeru.
- Úpravy probíhají pouze v `~/.local/share/applications/`, systémové soubory zůstávají nedotčené.
- Před každou změnou vytvoří zálohu s možností rollbacku a podporuje `--dry-run` náhled.
- Generuje složky kategorií přímo do Elephant/Walker konfigurace.

## Instalace

### 1. Základní setup

```bash
cd ~/Work
git clone https://github.com/Richieee-0006/CatWalker.git CatWalker
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

### 2. Systémový alias (volitelné)

Zpřístupnění `catwalker` z libovolného adresáře:

```bash
ln -s "$(pwd)/catwalker" ~/.local/bin/catwalker
echo $PATH | grep ".local/bin"
```

### 3. Shell auto-completion (Bash)

```bash
echo 'source <(catwalker --generate-completions)' >> ~/.bashrc
```

## Použití

Wrapper `catwalker` automaticky aktivuje `.venv`:

```bash
catwalker --help          # Nápověda
catwalker categories      # Seznam kategorií
```

### Kategorizace aplikací

```bash
# Náhled (dry-run)
catwalker categorize

# Aplikovat na nekategorizované aplikace
catwalker categorize --apply

# Rekategorizovat vše znovu
catwalker categorize --recategorize --apply
```

### Vygenerování Walker menu

```bash
# Vygeneruje ~/.config/elephant/menus/catwalker_*.toml
# a aktualizuje ~/.config/walker/config.toml
catwalker menus

# Náhled
catwalker menus --dry-run

# Smazání vygenerovaných souborů
catwalker menus --clean
```

Restart Walkeru: `killall walker; sleep 1 && walker &`

## Architektura

```
parser.py          # Parsuje .desktop soubory
categorizer.py     # Volá Google AI REST API (přes requests)
writer.py          # Upravuje Categories= pomocí regexu
menu_generator.py  # Generuje Elephant TOML menu a Walker config
main.py            # CLI rozhraní a router příkazů
config.py          # Konfigurace a cesty
catwalker          # Bash wrapper script
```

## Řešení problémů

### API klíč nefunguje
Ověřte proměnnou prostředí `GEMINI_API_KEY`: `echo $GEMINI_API_KEY`.

### .desktop soubory mají lowercase klíče
`writer.py` pomocí regexu opravuje velikost písmen standardních klíčů (např. `categories=` -> `Categories=`).

## Licence

MIT — richieee @ 2026
