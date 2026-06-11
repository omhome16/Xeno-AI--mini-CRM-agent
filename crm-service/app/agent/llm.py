"""
Groq LLM Client — Used for all agent tasks (reasoning, intent parsing, SQL generation, and message drafting).

Previously, this was a dual LLM setup, but Gemini was completely decommissioned due to reliability and rate limit issues.
"""

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Raised when the LLM provider fails."""
    pass


class GroqLLMClient:
    """
    Groq LLM client (previously Dual LLM Client, refactored to use Groq exclusively).
    """

    def __init__(self, groq_key: str = ""):
        self._groq_key = groq_key
        self._groq_client = None

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
        Use Groq for reasoning tasks (intent parsing, SQL generation).
        """
        groq = self._get_groq()
        if groq:
            try:
                # Only use JSON mode if response_schema is provided, or if the prompt requests JSON
                use_json = response_schema is not None or "json" in system_prompt.lower()
                fmt = {"type": "json_object"} if use_json else None
                result = await self._call_groq(
                    system_prompt,
                    user_input,
                    response_format=fmt,
                )
                if result:
                    return result
            except Exception as e:
                logger.error(f"Groq reasoning execution failed: {e}")
                raise e

        raise LLMError("Groq provider not configured or failed for reasoning task")

    async def generate(
        self,
        system_prompt: str,
        user_input: str,
    ) -> str:
        """
        Use Groq for fast text generation (message drafting).
        """
        groq = self._get_groq()
        if groq:
            try:
                result = await self._call_groq(system_prompt, user_input)
                if result:
                    return result
            except Exception as e:
                logger.error(f"Groq generation failed: {e}")
                raise e

        raise LLMError("Groq provider not configured or failed for generation task")

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
        ]

        def _sync_call(model_name: str, use_json_format: bool = True):
            # Ensure "json" is present if we are requesting JSON format to avoid Groq 400 error
            sys_prompt = system_prompt
            if response_format and use_json_format and "json" not in sys_prompt.lower() and "json" not in user_input.lower():
                sys_prompt += "\n\nReturn the response as a JSON object."

            kwargs = {
                "model": model_name,
                "messages": [
                    {"role": "system", "content": sys_prompt},
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
            for attempt in range(2):  # Try each model up to 2 times if rate limited
                try:
                    result = await asyncio.to_thread(_sync_call, model, True)
                    if result is not None:
                        logger.debug(f"Groq ({model}) response: {result[:200]}...")
                        return result
                except Exception as e:
                    err_str = str(e).lower()
                    last_error = e

                    # 1. Check if it's a rate limit error (429)
                    if "429" in err_str or "rate_limit" in err_str or "limit" in err_str or "exhaust" in err_str or "rate limit" in err_str:
                        if attempt == 0:
                            logger.warning(f"Groq ({model}) hit rate limit, retrying after 1.5s backoff...")
                            await asyncio.sleep(1.5)
                            continue  # Retry same model
                        else:
                            logger.warning(f"Groq ({model}) rate limit retry failed. Trying next model...")
                            break  # Move to next model

                    # 2. Check if it's a JSON formatting requirement error
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
                        break  # Move to next model

                    # 3. For other exceptions, try the next model
                    logger.warning(f"Groq ({model}) failed: {e}. Trying next model...")
                    break

        # If all models in the list failed, raise the last encountered error
        if last_error:
            raise last_error
        return None

    @property
    def is_configured(self) -> bool:
        """Check if Groq is configured."""
        return bool(self._groq_key)

    @property
    def available_providers(self) -> list[str]:
        """List configured providers."""
        providers = []
        if self._groq_key:
            providers.append("groq")
        return providers


# Alias for backward compatibility
DualLLMClient = GroqLLMClient

