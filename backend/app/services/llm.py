"""Unified LLM client — Gemini primary → Groq fallback → OpenRouter last resort."""
import time
import logging

from google import genai
from google.genai import errors as genai_errors
import openai

from app.core.config import settings

logger = logging.getLogger(__name__)

gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

groq_client = openai.OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=settings.GROQ_API_KEY,
) if settings.GROQ_API_KEY else None

openrouter_client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=settings.OPENROUTER_API_KEY,
) if settings.OPENROUTER_API_KEY else None

# Gemini models to try (in order)
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-flash-lite",
]

# Groq models — fast, free, high limits (14,400 req/day)
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "gemma2-9b-it",
    "llama-3.1-8b-instant",
]

# Free OpenRouter fallback models (last resort)
FALLBACK_MODELS = [
    "google/gemma-3-27b-it:free",
    "google/gemma-3-4b-it:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
]

# Track rate limits per model to avoid re-hitting them
_model_rate_limited_until: dict[str, float] = {}


def _is_rate_limited(model: str) -> bool:
    return time.time() < _model_rate_limited_until.get(model, 0)


def _mark_rate_limited(model: str, cooldown: int = 120):
    _model_rate_limited_until[model] = time.time() + cooldown


def generate(prompt: str, max_tokens: int = 2048) -> str:
    """Generate text using Gemini → Groq → OpenRouter fallback chain."""

    # 1. Try Gemini models
    for model in GEMINI_MODELS:
        if _is_rate_limited(model):
            continue
        try:
            response = gemini_client.models.generate_content(
                model=model,
                contents=prompt,
            )
            return response.text
        except genai_errors.ClientError as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                _mark_rate_limited(model)
                logger.warning(f"Gemini {model} rate-limited, trying next")
            else:
                logger.error(f"Gemini {model} error: {e}")
        except Exception as e:
            logger.error(f"Gemini {model} error: {e}")

    # 2. Try Groq models (fast, 14,400 req/day free)
    if groq_client:
        for model in GROQ_MODELS:
            if _is_rate_limited(f"groq:{model}"):
                continue
            try:
                response = groq_client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                logger.info(f"Using Groq: {model}")
                return response.choices[0].message.content
            except Exception as e:
                if "429" in str(e) or "rate_limit" in str(e).lower():
                    _mark_rate_limited(f"groq:{model}", cooldown=60)
                    logger.warning(f"Groq {model} rate-limited, trying next")
                else:
                    logger.error(f"Groq {model} error: {e}")
                continue

    # 3. Try OpenRouter free models (last resort)
    if openrouter_client:
        for model in FALLBACK_MODELS:
            if _is_rate_limited(f"or:{model}"):
                continue
            try:
                response = openrouter_client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )
                logger.info(f"Using OpenRouter fallback: {model}")
                return response.choices[0].message.content
            except Exception as e:
                if "429" in str(e):
                    _mark_rate_limited(f"or:{model}", cooldown=60)
                logger.debug(f"Fallback {model} failed: {e}")
                continue

    raise RuntimeError("All LLM providers exhausted. Try again in a few minutes.")
