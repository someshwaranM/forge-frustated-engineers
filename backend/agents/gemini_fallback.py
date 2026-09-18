"""
Vigil — Phase 7: Gemini Fallback Provider for Investigator Agent.

Provides the same-schema Gemini fallback for forensic compliance investigations.
Maintains identical validation, guardrails, and deterministic parameters (temperature=0.0).
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional
import google.generativeai as genai
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Ensure .env is loaded
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(ENV_PATH)


def _clean_json_text(text: str) -> str:
    """Strip markdown code fences and extraneous leading/trailing whitespace."""
    text = text.strip()
    if text.startswith("```"):
        # Strip ```json or ``` at beginning and ``` at end
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


class GeminiInvestigatorClient:
    """Client for executing forensic evaluations against Google Gemini models."""

    def __init__(self, api_key: Optional[str] = None, model_id: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in environment or .env")

        self.model_id = model_id or os.getenv("GEMINI_MODEL_ID", "gemini-3.5-flash")
        # Handle 'models/' prefix if present
        if self.model_id.startswith("models/"):
            self.model_id = self.model_id[len("models/"):]

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(
            model_name=self.model_id,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.0,
            },
        )

    def evaluate(self, prompt: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        Execute investigation prompt and return parsed JSON dictionary.
        Includes automatic retry and backoff on rate-limit / quota errors.
        """
        import time

        for attempt in range(max_retries):
            try:
                logger.info(f"Invoking Gemini fallback model '{self.model_id}' (attempt {attempt+1}/{max_retries})...")
                response = self.model.generate_content(prompt)

                if not response or not response.text:
                    raise RuntimeError("Gemini returned empty or null response")

                raw_text = _clean_json_text(response.text)
                try:
                    result = json.loads(raw_text)
                    if not isinstance(result, dict):
                        raise ValueError(f"Expected JSON object, got {type(result).__name__}")
                    return result
                except json.JSONDecodeError as exc:
                    logger.error(f"Failed to parse Gemini response as JSON: {raw_text}")
                    raise ValueError(f"Gemini output is not valid JSON: {exc}") from exc

            except Exception as exc:
                err_str = str(exc)
                if ("429" in err_str or "quota" in err_str.lower()) and attempt < max_retries - 1:
                    delay = 15.0
                    match = re.search(r"retry in ([\d\.]+)s", err_str, re.IGNORECASE)
                    if match:
                        delay = float(match.group(1)) + 2.0
                    logger.warning(f"Rate limited (429). Sleeping for {delay:.1f}s before retry...")
                    time.sleep(delay)
                else:
                    raise


def call_gemini_investigator(prompt: str) -> Dict[str, Any]:
    """Convenience helper to evaluate candidate via Gemini fallback."""
    client = GeminiInvestigatorClient()
    return client.evaluate(prompt)
