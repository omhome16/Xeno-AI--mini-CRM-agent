"""
Gemini LLM Client — Supports Gemini 2.5 Flash as the sole model provider.

If GEMINI_API_KEY is found in the environment, it uses Gemini 2.5 Flash
(via direct async HTTPX calls).

Public API:
  client.reason(system_prompt, user_input)   → Always returns JSON string
  client.generate(system_prompt, user_input) → Returns free-text string
"""

import asyncio
import logging
import os
import httpx

logger = logging.getLogger(__name__)

_TEMPERATURE = 0.3
_MAX_TOKENS = 2048
_RATE_LIMIT_BACKOFF_SECS = 2.0


class LLMError(Exception):
    """Raised when the Gemini LLM provider is unavailable or all retries are exhausted."""
    pass


class GeminiLLMClient:
    """
    Gemini LLM Client utilizing Gemini 2.5 Flash.

    Usage:
        client = GeminiLLMClient(gemini_key="AQ...")
        json_str = await client.reason(system_prompt, user_input)
        text     = await client.generate(system_prompt, user_input)
    """

    def __init__(self, gemini_key: str = "", model_id: str = ""):
        try:
            from app.config import get_settings
            settings = get_settings()
            self._gemini_key = gemini_key or getattr(settings, "GEMINI_API_KEY", "") or ""
        except Exception:
            self._gemini_key = gemini_key or os.environ.get("GEMINI_API_KEY") or ""

    # ── Public Methods ────────────────────────────────────────────────────────

    async def reason(self, system_prompt: str, user_input: str) -> str:
        """
        Structured reasoning — always returns a JSON string.
        """
        return await self._call_gemini(system_prompt, user_input, want_json=True)

    async def generate(self, system_prompt: str, user_input: str) -> str:
        """
        Free-text generation — returns a plain string.
        """
        return await self._call_gemini(system_prompt, user_input, want_json=False)

    # ── Gemini Async API Call ──────────────────────────────────────────────────

    async def _call_gemini(self, system_prompt: str, user_input: str, want_json: bool) -> str:
        """
        Direct async HTTP call to Google's Gemini 2.5 Flash API.
        """
        if not self._gemini_key:
            raise LLMError("Gemini API key is not configured. Set GEMINI_API_KEY.")

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        
        generation_config = {
            "temperature": _TEMPERATURE,
            "maxOutputTokens": _MAX_TOKENS,
        }
        if want_json:
            generation_config["responseMimeType"] = "application/json"

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_input}]
                }
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": generation_config
        }
        
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._gemini_key
        }

        last_error = None
        for attempt in range(2):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(url, json=payload, headers=headers)
                    if response.status_code == 429:
                        logger.warning(f"[Gemini] Rate limit hit. Attempt {attempt + 1}. Backing off...")
                        await asyncio.sleep(_RATE_LIMIT_BACKOFF_SECS)
                        continue
                    
                    if response.status_code != 200:
                        raise LLMError(f"Gemini API error (Status {response.status_code}): {response.text}")
                    
                    data = response.json()
                    try:
                        content = data["candidates"][0]["content"]["parts"][0]["text"]
                        if not content or not content.strip():
                            raise LLMError("Gemini returned an empty response.")
                        logger.debug(f"[Gemini] OK: {content[:100]}...")
                        return content
                    except (KeyError, IndexError) as parse_err:
                        raise LLMError(f"Failed to parse Gemini response structure: {data}") from parse_err

            except Exception as e:
                last_error = e
                logger.warning(f"[Gemini] Error on attempt {attempt + 1}: {e}")
                if attempt == 0:
                    await asyncio.sleep(0.5)

        raise LLMError(f"Gemini call failed after 2 attempts. Last error: {last_error}")

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        """True if a Gemini API key is set."""
        return bool(self._gemini_key)

    @property
    def available_providers(self) -> list[str]:
        """List of configured LLM providers."""
        providers = []
        if self._gemini_key:
            providers.append("gemini")
        return providers


# Backward-compatibility aliases
GeminiLLMClient = GeminiLLMClient
DualLLMClient = GeminiLLMClient