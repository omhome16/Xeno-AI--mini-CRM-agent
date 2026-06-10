"""
Chat API Router — The main AI agent interface.

Endpoints:
  POST /api/chat          — Start a new agent conversation
  POST /api/chat/resume   — Resume an interrupted conversation (human-in-the-loop)
  GET  /api/chat/stream/:id — SSE stream for real-time updates

Flow:
  1. Frontend sends user message to POST /api/chat
  2. Backend starts the LangGraph workflow as a background task
  3. Frontend connects to GET /api/chat/stream/:id for real-time updates
  4. When the agent hits an interrupt (human-in-the-loop), it sends an interrupt event
  5. Frontend shows the interrupt card, user responds
  6. Frontend sends response to POST /api/chat/resume
  7. Workflow continues from where it was interrupted
"""

import json
import logging
import asyncio
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Any

from app.config import get_settings
from app.agent.llm import DualLLMClient
from app.agent.graph import build_campaign_graph
from app.agent.state import CampaignState
from app.sse.manager import push_event, event_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# ── In-memory state store (Redis in production) ──
# Maps conversation_id → last graph state snapshot
_conversation_states: dict[str, dict] = {}
_conversation_configs: dict[str, dict] = {}


# ── Request/Response Models ──

class ChatRequest(BaseModel):
    """Request to start a new chat or send a message."""
    message: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field(default="guided", pattern="^(guided|autopilot)$")
    conversation_id: Optional[str] = None


class ResumeRequest(BaseModel):
    """Request to resume an interrupted conversation."""
    conversation_id: str
    response: dict = Field(
        ..., description="User's response to the interrupt (action + data)"
    )


class ChatResponse(BaseModel):
    """Initial response with conversation ID for SSE connection."""
    conversation_id: str
    status: str = "processing"
    message: str = "Agent is working on your request. Connect to the SSE stream for updates."


# ── Background task: Run the graph ──

async def _run_graph(
    conversation_id: str,
    state: CampaignState,
    llm_client: DualLLMClient,
    resume_value: Any = None,
) -> None:
    """
    Run the LangGraph workflow as a background task.

    Streams events to the SSE queue as the graph progresses.
    When an interrupt is hit, sends the interrupt data and pauses.
    """
    try:
        graph = build_campaign_graph(llm_client)

        await push_event(conversation_id, "step_start", {
            "step": "Starting agent workflow",
            "message": f"Processing: {state.get('user_message', '')[:100]}",
        })

        # Run graph with interrupt support
        config = {"configurable": {"thread_id": conversation_id}}

        if resume_value is not None:
            # Resuming from interrupt
            from langgraph.types import Command
            result_events = []
            async for event in graph.astream(
                Command(resume=resume_value),
                config=config,
            ):
                result_events.append(event)
                await _process_graph_event(conversation_id, event)
        else:
            # Fresh start
            result_events = []
            async for event in graph.astream(state, config=config):
                result_events.append(event)
                await _process_graph_event(conversation_id, event)

        # Check if we ended with an interrupt
        snapshot = graph.get_state(config)
        if snapshot.next:
            # Graph is interrupted — save state for resume
            _conversation_states[conversation_id] = dict(snapshot.values)
            _conversation_configs[conversation_id] = config

            # The interrupt event was already sent by the node
            logger.info(f"Graph interrupted at: {snapshot.next}")
            return

        # Graph completed normally
        final_state = snapshot.values if snapshot else {}
        await push_event(conversation_id, "result", {
            "step": "complete",
            "state": _serialize_state(final_state),
        })

    except Exception as e:
        logger.error(f"Graph execution error: {e}", exc_info=True)
        await push_event(conversation_id, "error", {
            "message": f"Agent error: {str(e)[:300]}",
        })


async def _process_graph_event(conversation_id: str, event: dict) -> None:
    """Process a single graph stream event and push to SSE."""
    for node_name, node_output in event.items():
        if node_name == "__interrupt__":
            # LangGraph interrupt — extract the value as a plain dict
            if isinstance(node_output, (list, tuple)) and node_output:
                item = node_output[0]
                interrupt_data = item.value if hasattr(item, 'value') else item
            else:
                interrupt_data = node_output

            # Ensure interrupt_data is a plain dict
            if not isinstance(interrupt_data, dict):
                interrupt_data = {"raw": str(interrupt_data)}
            else:
                interrupt_data = _serialize_state(interrupt_data)

            await push_event(conversation_id, "interrupt", interrupt_data)
            logger.info(f"Interrupt sent: {type(interrupt_data)}")
        else:
            # Normal node completion
            await push_event(conversation_id, "step_complete", {
                "step": node_name,
                "data": _serialize_state(node_output) if isinstance(node_output, dict) else str(node_output),
            })


def _serialize_state(state: dict) -> dict:
    """Serialize state for JSON transmission (handle UUIDs, datetimes, Decimals, etc.)."""
    from decimal import Decimal
    from uuid import UUID

    def _convert(value):
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, UUID):
            return str(value)
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        if isinstance(value, dict):
            return {k: _convert(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [_convert(v) for v in value[:20]]  # Cap list size
        # Fallback for any unknown type (Interrupt, etc.)
        return str(value)

    return {k: _convert(v) for k, v in state.items()}


# ── Endpoints ──

@router.post(
    "",
    response_model=ChatResponse,
    status_code=202,
    summary="Start a new chat",
)
async def start_chat(request: ChatRequest):
    """
    Start a new agent conversation.

    Returns a conversation_id immediately. Connect to
    GET /api/chat/stream/{conversation_id} for real-time updates.
    """
    settings = get_settings()
    conversation_id = request.conversation_id or uuid4().hex

    # Build initial state
    state: CampaignState = {
        "user_message": request.message,
        "mode": request.mode,
        "conversation_id": conversation_id,
        "messages": [],
        "current_step": "starting",
    }

    # Initialize LLM client
    llm_client = DualLLMClient(
        gemini_key=settings.GEMINI_API_KEY,
        groq_key=settings.GROQ_API_KEY,
    )

    if not llm_client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="No LLM providers configured. Set GEMINI_API_KEY or GROQ_API_KEY.",
        )

    # Start graph as background task
    asyncio.create_task(
        _run_graph(conversation_id, state, llm_client),
        name=f"chat-{conversation_id[:8]}",
    )

    return ChatResponse(
        conversation_id=conversation_id,
        status="processing",
    )


@router.post(
    "/resume",
    response_model=ChatResponse,
    status_code=202,
    summary="Resume an interrupted conversation",
)
async def resume_chat(request: ResumeRequest):
    """
    Resume a conversation from a human-in-the-loop interrupt.

    The frontend sends the user's response to the interrupt
    (approve, edit, cancel), and the graph continues.
    """
    settings = get_settings()
    conversation_id = request.conversation_id

    saved_state = _conversation_states.get(conversation_id)
    if not saved_state:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found or no pending interrupt",
        )

    llm_client = DualLLMClient(
        gemini_key=settings.GEMINI_API_KEY,
        groq_key=settings.GROQ_API_KEY,
    )

    # Resume graph with user's response
    asyncio.create_task(
        _run_graph(conversation_id, saved_state, llm_client, resume_value=request.response),
        name=f"chat-resume-{conversation_id[:8]}",
    )

    # Clean up saved state
    _conversation_states.pop(conversation_id, None)

    return ChatResponse(
        conversation_id=conversation_id,
        status="resuming",
        message="Resuming workflow with your response.",
    )


@router.get(
    "/stream/{conversation_id}",
    summary="SSE stream for real-time updates",
)
async def chat_stream(conversation_id: str):
    """
    Server-Sent Events stream for a conversation.

    Connect to this endpoint after starting a chat to receive
    real-time updates as the agent processes the workflow.

    Event types:
      - step_start: Agent started a new step
      - step_complete: Agent finished a step (includes data)
      - interrupt: Agent paused for human review (includes interrupt card data)
      - result: Final result
      - error: Something went wrong
      - heartbeat: Keep-alive (every 15s)
    """
    return StreamingResponse(
        event_stream(conversation_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
