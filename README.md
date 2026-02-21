# CatWalker 🐱

Automatická kategorizace Linuxových aplikací pro Walker pomocí Gemini Flash LLM.

## Features

- 🤖 **Inteligentní kategorizace** - Používá Gemini Flash k chytré kategorizaci aplikací
- 🔒 **Bezpečné** - Nikdy nemodifikuje systémové soubory, vše v `~/.local/share/applications/`
- 💾 **Automatický backup** - Před každou změnou vytvoří zálohu
- 🔄 **Rollback** - Snadné vrácení změn
- 🎯 **Dry-run mode** - Preview před aplikací změn
- ⚡ **Batch processing** - Efektivní zpracování velkého množství aplikací

## Instalace

```bash
# 1. Clone repo
cd ~/Work
git clone <repo-url> CatWalker
cd CatWalker

# 2. Nainstaluj závislosti
pip install -r requirements.txt

# 3. Získej Gemini API klíč
# https://aistudio.google.com/app/apikey

# 4. Nastav API klíč
export GEMINI_API_KEY='your-api-key-here'

# Přidej do ~/.bashrc nebo ~/.zshrc pro permanentní nastavení:
echo "export GEMINI_API_KEY='your-api-key-here'" >> ~/.bashrc
```

## Použití

### 1. Zobrazit aplikace

```bash
# Všechny aplikace
./main.py scan

# Jen nekategorizované
./main.py scan --uncategorized

# Limitovat výstup
./main.py scan --limit 20

# Filtrovat podle kategorie
./main.py scan --category Network
```

### 2. Kategorizovat aplikace

```bash
# Dry-run (preview bez změn)
./main.py categorize

# Aplikovat změny
./main.py categorize --apply

# Rekategorizovat všechny aplikace
./main.py categorize --recategorize --apply

# Testovat na 10 aplikacích
./main.py categorize --limit 10 --apply
```

### 3. Rollback změn

```bash
# Rollback na poslední backup
./main.py rollback

# Zobrazit dostupné backupy
./main.py rollback --list

# Rollback na konkrétní backup
./main.py rollback --timestamp 20260221_143022
```

### 4. Zobrazit kategorie

```bash
./main.py categories
```

## Jak to funguje

### Kategorie

Aplikace jsou automaticky tříděny do těchto kategorií:

- **Development** - IDE, editory, dev tools
- **System** - Systémové utility, monitoring
- **Media** - Audio, video, přehrávače
- **Office** - Dokumenty, tabulky, prezentace
- **Games** - Hry
- **Internet** - Browsery, chat, email
- **Graphics** - Grafické editory, prohlížeče
- **Utility** - Obecné utility
- **Settings** - Nastavení systému
- **Education** - Vzdělávací aplikace

### Architektura

1. **Parser** (`parser.py`) - Parsuje `.desktop` soubory z `/usr/share/applications/` a `~/.local/share/applications/`

2. **Categorizer** (`categorizer.py`) - Posílá aplikace Gemini Flash API pro kategorizaci
   - Extrahuje název, popis a další kontext
   - Gemini vrací strukturovaný JSON s kategoriemi
   - Validuje výstupy

3. **Writer** (`writer.py`) - Bezpečně aplikuje změny
   - Zkopíruje soubory do `~/.local/share/applications/`
   - Vytvoří backup před změnou
   - Modifikuje pouze `Categories=` pole
   - Zachová ostatní metadata

### Bezpečnost

- ✅ Nikdy nemodifikuje `/usr/share/applications/` (systémové soubory)
- ✅ Všechny změny jdou do `~/.local/share/applications/` (má přednost)
- ✅ Automatický backup před každou změnou
- ✅ Snadný rollback
- ✅ Dry-run mode pro preview

## Příklad workflow

```bash
# 1. Zjistit kolik máme nekategorizovaných aplikací
./main.py scan --uncategorized

# 2. Preview kategorizace na 10 aplikacích
./main.py categorize --limit 10

# 3. Vypadá dobře? Aplikovat!
./main.py categorize --limit 10 --apply

# 4. Restartovat Walker
killall walker && walker &

# 5. Nelíbí se? Rollback!
./main.py rollback
```

## Konfigurace

Úpravy v `config.py`:

```python
# Vlastní kategorie
DEFAULT_CATEGORIES = [
    "Development",
    "MyCustomCategory",
    # ...
]

# Jiný model
MODEL_NAME = "gemini-1.5-flash"

# Batch size pro API
# (kolik aplikací poslat najednou)
batch_size = 50  # default
```

## Troubleshooting

### API klíč nefunguje
```bash
# Zkontroluj že je nastaven
echo $GEMINI_API_KEY

# Nastav znovu
export GEMINI_API_KEY='your-key'
```

### Walker neukazuje změny
```bash
# Restart Walkera
killall walker && walker &

# Nebo restart Hyprlandu
hyprctl reload
```

### Chybí závislosti
```bash
pip install -r requirements.txt
```

## Free tier limity

Gemini Flash free tier:
- ✅ 15 requests/min
- ✅ 1500 requests/day
- ✅ 1 milion tokens/min

Pro kategorizaci desítek/stovek aplikací je to víc než dost! 🚀

## License

MIT

## Autor

richieee @ 2026
