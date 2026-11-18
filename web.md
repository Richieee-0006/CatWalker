# CatWalker

CLI tool that categorizes Linux `.desktop` applications using Google's Gemma 3 27B REST API and generates sorted menu folders for Walker and Elephant launchers.

## Key Features
- **LLM Categorization:** Classifies uncategorized `.desktop` entries via Google AI REST API without requiring the heavy Gemini SDK.
- **Usage-Based Sorting:** Orders categories and applications using Walker launch history.
- **Safe Edits & Rollback:** Modifies only `~/.local/share/applications/`, creates automatic backups, and supports `--dry-run`.
- **Walker & Elephant Menus:** Generates `catwalker_*.toml` menus for Elephant and updates Walker's `config.toml`.

## Tech Stack
- **Language:** Python 3, Bash
- **LLM API:** Google AI REST API (`gemma-3-27b-it` via `requests`)
- **Launchers:** Walker, Elephant
