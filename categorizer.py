import json
import logging
from typing import Dict, Optional
import time

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from config import (
    GEMINI_API_KEY,
    DEFAULT_CATEGORIES,
    MODEL_NAME,
    MAX_RETRIES,
    TIMEOUT,
    CATEGORIZATION_PROMPT,
    CATEGORY_MAPPINGS
)
from parser import DesktopEntry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AppCategorizer:
    """Categorizes applications using Gemini Flash LLM"""

    def __init__(self, api_key: Optional[str] = None):
        if not GEMINI_AVAILABLE:
            raise ImportError(
                "google-generativeai not installed. "
                "Install with: pip install google-generativeai"
            )

        self.api_key = api_key or GEMINI_API_KEY

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY not set. "
                "Set it via environment variable or pass to constructor."
            )

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(MODEL_NAME)
        logger.info(f"Initialized Gemini model: {MODEL_NAME}")

    def _build_prompt(self, entries: Dict[str, DesktopEntry]) -> str:
        """Build prompt for LLM"""
        # Format applications for prompt
        apps_text = []
        for filename, entry in entries.items():
            context = entry.get_context()
            apps_text.append(f"- {filename}: {context}")

        applications_str = "\n".join(apps_text)
        categories_str = ", ".join(DEFAULT_CATEGORIES)

        return CATEGORIZATION_PROMPT.format(
            categories=categories_str,
            applications=applications_str
        )

    def _parse_response(self, response_text: str) -> Optional[Dict[str, str]]:
        """Parse LLM response as JSON"""
        try:
            # Try to extract JSON from response
            # Sometimes LLM adds markdown code blocks
            text = response_text.strip()

            # Remove markdown code blocks if present
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]

            if text.endswith("```"):
                text = text[:-3]

            text = text.strip()

            # Parse JSON
            result = json.loads(text)

            # Validate categories
            for filename, category in result.items():
                if category not in DEFAULT_CATEGORIES:
                    logger.warning(
                        f"Invalid category '{category}' for {filename}, "
                        f"using 'Utility'"
                    )
                    result[filename] = "Utility"

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Response text: {response_text}")
            return None

    def categorize(
        self,
        entries: Dict[str, DesktopEntry],
        batch_size: int = 50
    ) -> Dict[str, str]:
        """
        Categorize applications using LLM

        Args:
            entries: Dictionary of desktop entries to categorize
            batch_size: Number of apps to process per API call

        Returns:
            Dictionary mapping filename to category
        """
        if not entries:
            logger.warning("No entries to categorize")
            return {}

        results = {}
        filenames = list(entries.keys())

        # Process in batches
        for i in range(0, len(filenames), batch_size):
            batch_filenames = filenames[i:i + batch_size]
            batch_entries = {f: entries[f] for f in batch_filenames}

            logger.info(
                f"Processing batch {i // batch_size + 1} "
                f"({len(batch_filenames)} apps)"
            )

            # Retry logic
            for attempt in range(MAX_RETRIES):
                try:
                    prompt = self._build_prompt(batch_entries)
                    response = self.model.generate_content(
                        prompt,
                        generation_config={
                            "temperature": 0.1,  # Low temperature for consistent results
                            "max_output_tokens": 2048,
                        }
                    )

                    batch_results = self._parse_response(response.text)

                    if batch_results:
                        results.update(batch_results)
                        logger.info(f"✓ Batch {i // batch_size + 1} successful")
                        break
                    else:
                        logger.warning(f"Failed to parse response (attempt {attempt + 1})")

                except Exception as e:
                    logger.error(f"API error (attempt {attempt + 1}): {e}")
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff

            # Rate limiting - be nice to the API
            time.sleep(1)

        logger.info(f"Categorized {len(results)} / {len(entries)} applications")
        return results

    def categorize_single(self, entry: DesktopEntry) -> str:
        """Categorize a single application"""
        results = self.categorize({entry.filename: entry})
        return results.get(entry.filename, "Utility")


def main():
    """Test categorizer"""
    from parser import DesktopFileParser

    # Check API key
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY environment variable not set")
        print("Set it with: export GEMINI_API_KEY='your-api-key'")
        return

    # Parse apps
    parser = DesktopFileParser()
    entries = parser.scan_all()

    # Get uncategorized or test with first 10
    test_entries = dict(list(entries.items())[:10])

    print(f"\n--- Testing with {len(test_entries)} applications ---\n")

    # Categorize
    categorizer = AppCategorizer()
    results = categorizer.categorize(test_entries)

    # Show results
    print("\n--- Results ---")
    for filename, category in results.items():
        entry = test_entries[filename]
        print(f"\n{entry.name} ({filename})")
        print(f"  Old: {', '.join(entry.categories) if entry.categories else 'None'}")
        print(f"  New: {category}")


if __name__ == "__main__":
    main()
