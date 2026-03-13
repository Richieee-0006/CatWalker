import json
import logging
import time
from typing import Dict
from typing import Optional

import requests

from config import CATEGORIZATION_PROMPT
from config import DEFAULT_CATEGORIES
from config import GEMINI_API_KEY
from config import GEMINI_API_URL
from config import MAX_RETRIES
from config import MODEL_NAME
from config import TIMEOUT
from parser import DesktopEntry

logger = logging.getLogger(__name__)

# google-genai dependency is no longer required due to direct REST API implementation
# for better UTF-8 handling and reduced dependency overhead.
GEMINI_AVAILABLE = True


class AppCategorizer:
    """Categorize applications using Google's Gemini API directly via REST."""
    
    def __init__(self, api_key: str = GEMINI_API_KEY):
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set.")
        self.url = GEMINI_API_URL.format(model=MODEL_NAME)
        logger.info(f"Initialized Gemini model: {MODEL_NAME}")

    def _build_prompt(self, entries: Dict[str, DesktopEntry]) -> str:
        apps_text = []
        for filename, entry in entries.items():
            # Using full context without lossy sanitization
            context = entry.get_context()
            apps_text.append(f"- {filename}: {context}")
        return CATEGORIZATION_PROMPT.format(
            categories=", ".join(DEFAULT_CATEGORIES),
            applications="\n".join(apps_text)
        )

    def _call_api(self, prompt: str) -> str:
        """Call Gemini API directly via REST requests to avoid SDK overhead and potential encoding issues."""
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
            # Handle markdown code blocks
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            
            result = json.loads(text.strip())
            
            # Validate categories and handle mismatches
            for filename, category in result.items():
                if category not in DEFAULT_CATEGORIES:
                    logger.warning(f"Invalid category '{category}' for {filename}, defaulting to 'Utility'")
                    result[filename] = "Utility"
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response from LLM: {e}")
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
                    logger.error(f"HTTP error during API call: {e.response.status_code} {e.response.text[:200]}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
                except Exception as e:
                    logger.error(f"Unexpected error during API call (attempt {attempt + 1}): {e}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)
            
            # Brief sleep between batches for rate compliance
            time.sleep(1)
        
        logger.info(f"Categorized {len(results)} / {len(entries)} applications")
        return results

    def categorize_single(self, entry: DesktopEntry) -> str:
        return self.categorize({entry.filename: entry}).get(entry.filename, "Utility")
