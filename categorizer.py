import json
import logging
import requests
from typing import Dict, Optional
import time

GEMINI_AVAILABLE = True

from config import (
    GEMINI_API_KEY, DEFAULT_CATEGORIES, MODEL_NAME,
    MAX_RETRIES, TIMEOUT, CATEGORIZATION_PROMPT, CATEGORY_MAPPINGS
)
from parser import DesktopEntry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class AppCategorizer:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GEMINI_API_KEY
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set.")
        self.url = GEMINI_API_URL.format(model=MODEL_NAME)
        logger.info(f"Initialized Gemini model: {MODEL_NAME}")

    def _sanitize(self, text: str) -> str:
        """Replace non-ASCII characters to avoid encoding issues"""
        return text.encode('ascii', errors='replace').decode('ascii')

    def _build_prompt(self, entries: Dict[str, DesktopEntry]) -> str:
        apps_text = []
        for filename, entry in entries.items():
            context = self._sanitize(entry.get_context())
            apps_text.append(f"- {filename}: {context}")
        return CATEGORIZATION_PROMPT.format(
            categories=", ".join(DEFAULT_CATEGORIES),
            applications="\n".join(apps_text)
        )

    def _call_api(self, prompt: str) -> str:
        """Call Gemini API directly via requests (bypasses SDK encoding bug on Python 3.14)"""
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
        }
        response = requests.post(
            self.url,
            params={"key": self.api_key},
            json=payload,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]

    def _parse_response(self, response_text: str) -> Optional[Dict[str, str]]:
        try:
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            result = json.loads(text.strip())
            for filename, category in result.items():
                if category not in DEFAULT_CATEGORIES:
                    logger.warning(f"Invalid category '{category}' for {filename}, using 'Utility'")
                    result[filename] = "Utility"
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            return None

    def categorize(self, entries: Dict[str, DesktopEntry], batch_size: int = 50) -> Dict[str, str]:
        if not entries:
            return {}
        results = {}
        filenames = list(entries.keys())
        for i in range(0, len(filenames), batch_size):
            batch = {f: entries[f] for f in filenames[i:i + batch_size]}
            logger.info(f"Processing batch {i // batch_size + 1} ({len(batch)} apps)")
            for attempt in range(MAX_RETRIES):
                try:
                    response_text = self._call_api(self._build_prompt(batch))
                    batch_results = self._parse_response(response_text)
                    if batch_results:
                        results.update(batch_results)
                        logger.info(f"✓ Batch {i // batch_size + 1} successful")
                        break
                    logger.warning(f"Failed to parse response (attempt {attempt + 1})")
                except requests.HTTPError as e:
                    logger.error(f"HTTP error: {e.response.status_code} {e.response.text[:200]}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
                except Exception as e:
                    logger.error(f"API error (attempt {attempt + 1}): {e}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
            time.sleep(1)
        logger.info(f"Categorized {len(results)} / {len(entries)} applications")
        return results

    def categorize_single(self, entry: DesktopEntry) -> str:
        return self.categorize({entry.filename: entry}).get(entry.filename, "Utility")


def main():
    from parser import DesktopFileParser
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set")
        return
    parser = DesktopFileParser()
    entries = parser.scan_all()
    test_entries = dict(list(entries.items())[:10])
    print(f"\n--- Testing with {len(test_entries)} applications ---\n")
    categorizer = AppCategorizer()
    results = categorizer.categorize(test_entries)
    print("\n--- Results ---")
    for filename, category in results.items():
        entry = test_entries[filename]
        print(f"\n{entry.name} ({filename})")
        print(f"  Old: {', '.join(entry.categories) if entry.categories else 'None'}")
        print(f"  New: {category}")


if __name__ == "__main__":
    main()
