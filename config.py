import os
from pathlib import Path

# API Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Paths
SYSTEM_APPS_DIR = Path("/usr/share/applications")
USER_APPS_DIR = Path.home() / ".local/share/applications"
BACKUP_DIR = Path.home() / ".local/share/catwalker/backups"

# Ensure directories exist
USER_APPS_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

# Default Categories
DEFAULT_CATEGORIES = [
    "Development",
    "System",
    "Media",
    "Office",
    "Games",
    "Internet",
    "Graphics",
    "Utility",
    "Settings",
    "Education"
]

# Category mappings for .desktop format (freedesktop.org standard)
CATEGORY_MAPPINGS = {
    "Development": "Development",
    "System": "System",
    "Media": "AudioVideo",
    "Office": "Office",
    "Games": "Game",
    "Internet": "Network",
    "Graphics": "Graphics",
    "Utility": "Utility",
    "Settings": "Settings",
    "Education": "Education"
}

# LLM Configuration
MODEL_NAME = "gemini-2.0-flash-exp"
MAX_RETRIES = 3
TIMEOUT = 30

# Prompt template
CATEGORIZATION_PROMPT = """You are an expert at categorizing Linux desktop applications.

I will provide you with a list of applications with their names and descriptions.
Your task is to categorize each application into ONE of these categories:
{categories}

Rules:
- Choose the MOST appropriate single category
- If unsure, use "Utility"
- Return ONLY valid JSON format
- Do not add explanations

Format your response as valid JSON:
{{
  "app_filename.desktop": "Category",
  "another_app.desktop": "Category"
}}

Applications to categorize:
{applications}

Return only the JSON object, nothing else."""
