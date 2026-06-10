"""
Callback Client — Fires delivery event webhooks to the CRM receipt API.

Handles retry with exponential backoff for resilience against
temporary CRM downtime. If all retries are exhausted, the event
is logged as a dead letter (in production, this would go to a
dead-letter queue like SQS or RabbitMQ).
"""

import httpx
import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Retry Configuration ──
MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 1.0  # 1s, 2s, 4s
TIMEOUT_SECONDS = 10.0


async def fire_callback(
    url: str,
    payload: dict[str, Any],
    max_retries: int = MAX_RETRIES,
) -> bool:
    """
    Send a delivery event callback to the CRM receipt API.

    Implements exponential backoff retry for resilience:
      Attempt 1: immediate
      Attempt 2: wait 1s
      Attempt 3: wait 2s
      Attempt 4: wait 4s (if max_retries=3, this is the last)

    Handles:
      - 200: Success — callback processed
      - 409: Duplicate — already processed (idempotency), treat as success
      - 4xx/5xx: Retryable error
      - Connection errors: Retryable

    Args:
        url: The CRM receipt API URL.
        payload: The delivery event payload.
        max_retries: Maximum number of retry attempts.

    Returns:
        True if callback was delivered successfully, False otherwise.
    """
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                response = await client.post(url, json=payload)

                if response.status_code == 200:
                    return True  # Success

                elif response.status_code == 409:
                    # Duplicate — CRM already processed this event
                    # This is expected when we retry and the first attempt
                    # actually succeeded but we didn't get the response
                    logger.debug(
                        f"Duplicate callback (idempotent): {payload.get('idempotency_key')}"
                    )
                    return True

                else:
                    logger.warning(
                        f"Callback attempt {attempt + 1}/{max_retries + 1} "
                        f"returned {response.status_code}: {response.text[:200]}"
                    )

        except httpx.ConnectError as e:
            logger.warning(
                f"Callback attempt {attempt + 1}/{max_retries + 1} "
                f"connection failed: {e}"
            )
        except httpx.TimeoutException as e:
            logger.warning(
                f"Callback attempt {attempt + 1}/{max_retries + 1} "
                f"timed out: {e}"
            )
        except Exception as e:
            logger.error(
                f"Callback attempt {attempt + 1}/{max_retries + 1} "
                f"unexpected error: {e}"
            )

        # ── Exponential backoff before retry ──
        if attempt < max_retries:
            backoff = BASE_BACKOFF_SECONDS * (2 ** attempt)
            logger.debug(f"Retrying in {backoff}s...")
            await asyncio.sleep(backoff)

    # ── All retries exhausted — dead letter ──
    logger.error(
        f"DEAD LETTER: Failed to deliver callback after {max_retries + 1} attempts. "
        f"Payload: communication_id={payload.get('communication_id')}, "
        f"event_type={payload.get('event_type')}, "
        f"idempotency_key={payload.get('idempotency_key')}"
    )
    # In production: push to dead-letter queue (SQS, RabbitMQ)
    return False
