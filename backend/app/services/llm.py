"""Unified LLM client with Gemini primary + OpenRouter fallback with multiple models."""
import time
import logging

from google import genai
from google.genai import errors as genai_errors
import openai

from app.core.config import settings

logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
openrouter_client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
)

GEMINI_MODEL = "gemini-2.5-flash"

# Free fallback models in priority order
FALLBACK_MODELS = [
    "google/gemma-3-27b-it:free",
    "google/gemma-3-4b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "qwen/qwen3-30b-a3b:free",
]

_rate_limited_until = 0.0


def generate(prompt: str, max_tokens: int = 2048) -> str:
    """Generate text using Gemini, falling back to OpenRouter free models if rate-limited."""
    global _rate_limited_until

    # Try Gemini first (if not currently rate-limited)
    if time.time() >= _rate_limited_until:
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            return response.text
        except genai_errors.ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                _rate_limited_until = time.time() + 120
                logger.warning("Gemini rate-limited, trying OpenRouter fallbacks")
            else:
                logger.error(f"Gemini error: {e}")
        except Exception as e:
            logger.error(f"Gemini error: {e}")

    # Try each fallback model
    for model in FALLBACK_MODELS:
        try:
            response = openrouter_client.chat.completions.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            logger.info(f"Using fallback model: {model}")
            return response.choices[0].message.content
        except Exception as e:
            logger.debug(f"Fallback {model} failed: {e}")
            continue

    # Last resort: wait and retry Gemini once
    logger.warning("All fallbacks failed, waiting 30s for Gemini retry...")
    time.sleep(30)
    try:
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        raise RuntimeError(f"All LLM providers exhausted: {e}")
