"""
Dual LLM Client — Gemini (reasoning) + Groq (fast generation) with fallback.

Architecture:
  - Gemini 2.0 Flash: Used for agent reasoning, intent parsing, SQL generation
    (structured output, schema compliance)
  - Groq (Llama 3): Used for fast message generation (speed over reasoning depth)

Fallback: If the primary provider fails (rate limit, timeout, error),
automatically falls back to the other provider. This ensures the agent
never fully breaks due to a single LLM provider issue.

Usage:
    client = DualLLMClient(gemini_key="...", groq_key="...")
    
    # For reasoning (intent parsing, SQL generation)
    result = await client.reason("Parse this user intent", user_input)
    
    # For fast generation (message drafting)
    result = await client.generate("Draft a WhatsApp message", context)
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when all LLM providers fail."""
    pass


class DualLLMClient:
    """
    Dual-provider LLM client with automatic fallback.

    Primary providers:
      - reason() → Gemini (structured output, complex reasoning)
      - generate() → Groq (fast text generation)

    If the primary fails, falls back to the other provider.
    """

    def __init__(self, gemini_key: str = "", groq_key: str = ""):
        self._gemini_key = gemini_key
        self._groq_key = groq_key
        self._gemini_client = None
        self._groq_client = None

    def _get_gemini(self):
        """Lazy-initialize Gemini client."""
        if self._gemini_client is None and self._gemini_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self._gemini_key)
                logger.info("Gemini client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini: {e}")
        return self._gemini_client

    def _get_groq(self):
        """Lazy-initialize Groq client."""
        if self._groq_client is None and self._groq_key:
            try:
                from groq import Groq
                self._groq_client = Groq(api_key=self._groq_key, max_retries=0)
                logger.info("Groq client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq: {e}")
        return self._groq_client

    async def reason(
        self,
        system_prompt: str,
        user_input: str,
        response_schema: Optional[dict] = None,
    ) -> str:
        """
        Use Gemini for reasoning tasks (intent parsing, SQL generation).
        Falls back to Groq if Gemini fails.

        Args:
            system_prompt: System instructions for the LLM.
            user_input: The user's input to process.
            response_schema: Optional JSON schema for structured output.

        Returns:
            LLM response text.
        """
        # Try Gemini first (primary for reasoning)
        gemini = self._get_gemini()
        if gemini:
            try:
                result = await self._call_gemini(system_prompt, user_input, response_schema)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Gemini reasoning failed, falling back to Groq: {e}")

        # Fallback to Groq
        groq = self._get_groq()
        if groq:
            try:
                result = await self._call_groq(
                    system_prompt,
                    user_input,
                    response_format={"type": "json_object"},
                )
                if result:
                    return result
            except Exception as e:
                logger.error(f"Groq fallback also failed: {e}")

        raise LLMError("All LLM providers failed for reasoning task")

    async def generate(
        self,
        system_prompt: str,
        user_input: str,
    ) -> str:
        """
        Use Groq for fast text generation (message drafting).
        Falls back to Gemini if Groq fails.

        Args:
            system_prompt: System instructions for generation.
            user_input: Context/parameters for generation.

        Returns:
            Generated text.
        """
        # Try Groq first (primary for generation — fast)
        groq = self._get_groq()
        if groq:
            try:
                result = await self._call_groq(system_prompt, user_input)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Groq generation failed, falling back to Gemini: {e}")

        # Fallback to Gemini
        gemini = self._get_gemini()
        if gemini:
            try:
                result = await self._call_gemini(system_prompt, user_input)
                if result:
                    return result
            except Exception as e:
                logger.error(f"Gemini fallback also failed: {e}")

        raise LLMError("All LLM providers failed for generation task")

    async def _call_gemini(
        self,
        system_prompt: str,
        user_input: str,
        response_schema: Optional[dict] = None,
    ) -> Optional[str]:
        """Call Gemini API."""
        import asyncio
        client = self._get_gemini()
        if not client:
            return None

        def _sync_call():
            from google.genai import types

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
                max_output_tokens=2048,
            )

            # Use structured output if schema provided
            if response_schema:
                config.response_mime_type = "application/json"
                config.response_schema = response_schema

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=user_input,
                config=config,
            )
            return response.text

        # Run sync SDK in thread pool to avoid blocking event loop
        result = await asyncio.to_thread(_sync_call)
        logger.debug(f"Gemini response: {result[:200]}...")
        return result

    async def _call_groq(
        self,
        system_prompt: str,
        user_input: str,
        response_format: Optional[dict] = None,
    ) -> Optional[str]:
        """Call Groq API with robust model cycling and JSON retry."""
        import asyncio
        client = self._get_groq()
        if not client:
            return None

        # Standard active Groq models in prioritized order
        models = [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
        ]

        def _sync_call(model_name: str, use_json_format: bool = True):
            kwargs = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input},
                ],
                "temperature": 0.3,
                "max_tokens": 2048,
            }
            if response_format and use_json_format:
                kwargs["response_format"] = response_format
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message.content

        last_error = None
        for model in models:
            # Try with JSON formatting constraint if response_format is provided
            try:
                result = await asyncio.to_thread(_sync_call, model, True)
                if result is not None:
                    logger.debug(f"Groq ({model}) response: {result[:200]}...")
                    return result
            except Exception as e:
                err_str = str(e).lower()
                last_error = e
                # If JSON validation failure occurs, retry this model without the response_format constraint
                if "json" in err_str or "format" in err_str or "validate" in err_str:
                    logger.warning(f"Groq ({model}) JSON mode failed, retrying without JSON formatting constraint: {e}")
                    try:
                        result = await asyncio.to_thread(_sync_call, model, False)
                        if result is not None:
                            logger.debug(f"Groq ({model}) response without JSON format: {result[:200]}...")
                            return result
                    except Exception as ex:
                        logger.warning(f"Groq ({model}) retry without JSON format also failed: {ex}")
                        last_error = ex
                else:
                    logger.warning(f"Groq ({model}) failed: {e}. Trying next model...")

        # If all models in the list failed, raise the last encountered error
        if last_error:
            raise last_error
        return None

    @property
    def is_configured(self) -> bool:
        """Check if at least one LLM provider is configured."""
        return bool(self._gemini_key or self._groq_key)

    @property
    def available_providers(self) -> list[str]:
        """List configured providers."""
        providers = []
        if self._gemini_key:
            providers.append("gemini")
        if self._groq_key:
            providers.append("groq")
        return providers
