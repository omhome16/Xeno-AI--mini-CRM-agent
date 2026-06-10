"""
SSE Manager — Server-Sent Events for real-time streaming.

Manages SSE connections per conversation, allowing the agent to
stream step-by-step updates to the frontend as the workflow progresses.

Architecture:
  - Each conversation gets its own asyncio.Queue
  - Events are pushed to the queue by agent nodes
  - The SSE endpoint reads from the queue and streams to the client
  - Queues are cleaned up when the client disconnects
"""

import asyncio
import json
import logging
from decimal import Decimal
from uuid import UUID
from typing import Any, AsyncGenerator


class _SafeEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal, UUID, datetime from asyncpg."""
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, UUID):
            return str(o)
        if hasattr(o, 'isoformat'):
            return o.isoformat()
        return super().default(o)

logger = logging.getLogger(__name__)

# Active SSE connections: conversation_id → asyncio.Queue
_connections: dict[str, asyncio.Queue] = {}


def get_or_create_queue(conversation_id: str) -> asyncio.Queue:
    """Get or create an SSE queue for a conversation."""
    if conversation_id not in _connections:
        _connections[conversation_id] = asyncio.Queue()
        logger.debug(f"Created SSE queue for conversation {conversation_id[:8]}")
    return _connections[conversation_id]


def remove_queue(conversation_id: str) -> None:
    """Remove an SSE queue when the client disconnects."""
    _connections.pop(conversation_id, None)
    logger.debug(f"Removed SSE queue for conversation {conversation_id[:8]}")


async def push_event(
    conversation_id: str,
    event_type: str,
    data: Any,
) -> None:
    """
    Push an event to a conversation's SSE queue.

    Event types:
      - step_start: Agent started a new workflow step
      - step_complete: Agent completed a workflow step
      - interrupt: Agent paused for human review
      - result: Final result from the agent
      - error: An error occurred
      - campaign_update: Live campaign delivery update
    """
    queue = _connections.get(conversation_id)
    if queue is None:
        logger.debug(f"No SSE listener for conversation {conversation_id[:8]}, dropping event")
        return

    event = {
        "type": event_type,
        "data": data,
    }

    await queue.put(event)
    logger.debug(f"Pushed SSE event: {event_type} to {conversation_id[:8]}")


async def event_stream(conversation_id: str) -> AsyncGenerator[str, None]:
    """
    Generate SSE events for a conversation.

    Yields formatted SSE strings ready for the HTTP response.
    Exits when a 'done' event is received or timeout.
    """
    queue = get_or_create_queue(conversation_id)

    try:
        while True:
            try:
                # Wait for events with timeout (heartbeat every 15s)
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
            except asyncio.TimeoutError:
                # Send heartbeat to keep connection alive
                yield f"event: heartbeat\ndata: {json.dumps({'type': 'heartbeat'})}\n\n"
                continue

            event_type = event.get("type", "message")
            data = json.dumps(event.get("data", {}), cls=_SafeEncoder)

            yield f"event: {event_type}\ndata: {data}\n\n"

            # End stream on terminal events
            if event_type in ("result", "error", "done"):
                break

    finally:
        remove_queue(conversation_id)
