"""
Chat API Router — The main AI agent interface (Campaign Studio).

Endpoints:
  POST /api/chat            — Brainstorm / query / general chat (no interrupts)
  POST /api/chat/plan       — Generate a campaign plan from a brief
  POST /api/chat/execute    — Execute an approved campaign end-to-end
  POST /api/chat/resume     — Resume an interrupted conversation (legacy, kept for safety)
  GET  /api/chat/stream/:id — SSE stream for real-time updates

Campaign Studio Flow:
  1. BRAINSTORM: User chats with AI → POST /api/chat (returns AI response + suggestions)
  2. PLAN: User clicks "Plan This Campaign" → POST /api/chat/plan (returns audience + message)
  3. EXECUTE: User clicks "Launch" → POST /api/chat/execute (runs campaign end-to-end)
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
from app.agent.prompts import IMPROVE_MESSAGE_PROMPT

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])

# ── In-memory state store (Redis in production) ──
_conversation_states: dict[str, dict] = {}
_conversation_configs: dict[str, dict] = {}


# ── Request/Response Models ──

class ChatRequest(BaseModel):
    """Request to start a new chat or send a message."""
    message: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field(default="brainstorm")
    conversation_id: Optional[str] = None
    history: list[dict] = Field(default_factory=list, description="Previous conversation messages for context")
    brief: dict = Field(default_factory=dict, description="Current campaign brief state")


class PlanRequest(BaseModel):
    """Request to generate a campaign plan from a brief."""
    brief: dict = Field(..., description="Campaign brief: {goal, audience, channel, message_idea, offer}")
    conversation_id: Optional[str] = None
    history: list[dict] = Field(default_factory=list)


class ExecuteRequest(BaseModel):
    """Request to execute a fully approved campaign."""
    brief: dict = Field(..., description="Campaign brief")
    audience_description: str = Field(..., description="Audience description for SQL generation")
    channel: str = Field(default="whatsapp")
    message_description: str = Field(default="")
    offer_details: str = Field(default="")
    message_template: Optional[str] = None
    conversation_id: Optional[str] = None


class ResumeRequest(BaseModel):
    """Request to resume an interrupted conversation (legacy)."""
    conversation_id: str
    response: dict = Field(
        ..., description="User's response to the interrupt (action + data)"
    )


class ChatResponse(BaseModel):
    """Initial response with conversation ID for SSE connection."""
    conversation_id: str
    status: str = "processing"
    message: str = "Agent is working on your request. Connect to the SSE stream for updates."


class ImproveMessageRequest(BaseModel):
    """Request to improve a message template based on instructions."""
    message_template: str = Field(..., description="The original drafted message template")
    instruction: str = Field(..., description="Natural language instructions/feedback for improvement")
    channel: str = Field(..., description="Campaign channel (whatsapp, sms, email, rcs)")
    audience_description: Optional[str] = Field(default="", description="Audience description")
    offer_details: Optional[str] = Field(default="", description="Offer/discount details")


class ImproveMessageResponse(BaseModel):
    """Response containing the improved message."""
    improved_message: str


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
    """
    try:
        graph = build_campaign_graph(llm_client)

        await push_event(conversation_id, "step_start", {
            "step": "Starting",
            "message": f"Processing: {state.get('user_message', '')[:100]}",
        })

        config = {"configurable": {"thread_id": conversation_id}}

        if resume_value is not None:
            from langgraph.types import Command
            async for event in graph.astream(
                Command(resume=resume_value),
                config=config,
            ):
                await _process_graph_event(conversation_id, event)
        else:
            async for event in graph.astream(state, config=config):
                await _process_graph_event(conversation_id, event)

        # Check if we ended with an interrupt
        snapshot = graph.get_state(config)
        if snapshot.next:
            _conversation_states[conversation_id] = dict(snapshot.values)
            _conversation_configs[conversation_id] = config
            logger.info(f"Graph interrupted at: {snapshot.next}")
            return

        # Graph completed — send result
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
            if isinstance(node_output, (list, tuple)) and node_output:
                item = node_output[0]
                interrupt_data = item.value if hasattr(item, 'value') else item
            else:
                interrupt_data = node_output

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
    """Serialize state for JSON transmission."""
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
            return [_convert(v) for v in value[:50]]
        return str(value)

    return {k: _convert(v) for k, v in state.items()}


# ── Endpoints ──

@router.post(
    "",
    response_model=ChatResponse,
    status_code=202,
    summary="Brainstorm, query, or chat with the AI agent",
)
async def start_chat(request: ChatRequest):
    """
    Send a message to the AI agent.

    In Campaign Studio, this handles:
    - Brainstorm: AI responds with suggestions and brief updates
    - Query: AI runs SQL and returns customer data
    - General chat: AI answers questions about the CRM
    """
    settings = get_settings()
    conversation_id = request.conversation_id or uuid4().hex

    state: CampaignState = {
        "user_message": request.message,
        "mode": request.mode,
        "conversation_id": conversation_id,
        "messages": request.history[-10:],
        "brief": request.brief,
        "current_step": "starting",
    }

    llm_client = DualLLMClient(
        gemini_key=settings.GEMINI_API_KEY,
        groq_key=settings.GROQ_API_KEY,
    )

    if not llm_client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="No LLM providers configured. Set GEMINI_API_KEY or GROQ_API_KEY.",
        )

    asyncio.create_task(
        _run_graph(conversation_id, state, llm_client),
        name=f"chat-{conversation_id[:8]}",
    )

    return ChatResponse(
        conversation_id=conversation_id,
        status="processing",
    )


@router.post(
    "/plan",
    response_model=ChatResponse,
    status_code=202,
    summary="Generate a campaign plan from a brief",
)
async def plan_campaign(request: PlanRequest):
    """
    Generate a campaign plan: build audience segment + draft message.

    Takes a campaign brief and returns:
    - Audience SQL + count + preview
    - Drafted message
    - Segment metadata
    """
    settings = get_settings()
    conversation_id = request.conversation_id or uuid4().hex

    brief = request.brief
    audience = brief.get("audience", "all customers")
    channel = brief.get("channel", "whatsapp")
    message_idea = brief.get("message_idea", "")
    offer = brief.get("offer", "")

    state: CampaignState = {
        "user_message": f"Create campaign for: {audience}",
        "mode": "plan",
        "conversation_id": conversation_id,
        "messages": request.history[-10:],
        "brief": brief,
        "action": "create_campaign",  # Skip intent parsing — go straight to build
        "audience_description": audience,
        "message_description": message_idea or offer or f"Campaign message for {audience}",
        "channel": channel,
        "offer_details": offer,
        "current_step": "planning",
    }

    llm_client = DualLLMClient(
        gemini_key=settings.GEMINI_API_KEY,
        groq_key=settings.GROQ_API_KEY,
    )

    if not llm_client.is_configured:
        raise HTTPException(status_code=503, detail="No LLM providers configured.")

    asyncio.create_task(
        _run_graph(conversation_id, state, llm_client),
        name=f"plan-{conversation_id[:8]}",
    )

    return ChatResponse(
        conversation_id=conversation_id,
        status="planning",
        message="Generating campaign plan...",
    )


@router.post(
    "/execute",
    response_model=ChatResponse,
    status_code=202,
    summary="Execute an approved campaign end-to-end",
)
async def execute_campaign(request: ExecuteRequest):
    """
    Execute a fully approved campaign.

    Takes the complete campaign spec and runs:
    build_segment → draft_message → execute_campaign → END
    """
    settings = get_settings()
    conversation_id = request.conversation_id or uuid4().hex

    state: CampaignState = {
        "user_message": f"Execute campaign: {request.audience_description}",
        "mode": "execute",
        "conversation_id": conversation_id,
        "action": "create_campaign",
        "audience_description": request.audience_description,
        "message_description": request.message_description or request.brief.get("message_idea", ""),
        "channel": request.channel,
        "offer_details": request.offer_details or request.brief.get("offer", ""),
        "message_template": request.message_template,
        "brief": request.brief,
        "current_step": "executing",
    }

    llm_client = DualLLMClient(
        gemini_key=settings.GEMINI_API_KEY,
        groq_key=settings.GROQ_API_KEY,
    )

    if not llm_client.is_configured:
        raise HTTPException(status_code=503, detail="No LLM providers configured.")

    asyncio.create_task(
        _run_graph(conversation_id, state, llm_client),
        name=f"exec-{conversation_id[:8]}",
    )

    return ChatResponse(
        conversation_id=conversation_id,
        status="executing",
        message="Launching campaign...",
    )


@router.post(
    "/improve-message",
    response_model=ImproveMessageResponse,
    summary="Improve a campaign message template with AI based on instructions",
)
async def improve_message(request: ImproveMessageRequest):
    """
    Improve a message template using the LLM according to the user's natural language instructions.
    """
    settings = get_settings()
    llm_client = DualLLMClient(
        gemini_key=settings.GEMINI_API_KEY,
        groq_key=settings.GROQ_API_KEY,
    )

    if not llm_client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="No LLM providers configured. Set GEMINI_API_KEY or GROQ_API_KEY.",
        )

    # Prepare prompt safely replacing variables without .format() KeyError risks
    prompt = IMPROVE_MESSAGE_PROMPT.replace("{message_template}", request.message_template).replace("{instruction}", request.instruction)

    context = (
        f"Channel: {request.channel}\n"
        f"Audience description: {request.audience_description or 'None'}\n"
        f"Offer details: {request.offer_details or 'None'}"
    )

    try:
        improved = await llm_client.generate(
            system_prompt=prompt,
            user_input=context,
        )
        if not improved:
            raise HTTPException(status_code=500, detail="AI returned an empty response.")
        return ImproveMessageResponse(improved_message=improved.strip())
    except Exception as e:
        logger.error(f"Message improvement error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to improve message: {str(e)}")


@router.post(
    "/resume",
    response_model=ChatResponse,
    status_code=202,
    summary="Resume an interrupted conversation",
)
async def resume_chat(request: ResumeRequest):
    """
    Resume a conversation from a human-in-the-loop interrupt (legacy).
    Returns a soft 200 if conversation not found (fixes double-resume bug).
    """
    settings = get_settings()
    conversation_id = request.conversation_id

    saved_state = _conversation_states.get(conversation_id)
    if not saved_state:
        # Soft response instead of 404 — fixes double-resume bug
        return ChatResponse(
            conversation_id=conversation_id,
            status="already_completed",
            message="This conversation has already completed or no pending interrupt.",
        )

    llm_client = DualLLMClient(
        gemini_key=settings.GEMINI_API_KEY,
        groq_key=settings.GROQ_API_KEY,
    )

    # Clean up before resuming to prevent double-resume
    _conversation_states.pop(conversation_id, None)
    _conversation_configs.pop(conversation_id, None)

    asyncio.create_task(
        _run_graph(conversation_id, saved_state, llm_client, resume_value=request.response),
        name=f"chat-resume-{conversation_id[:8]}",
    )

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

    Event types:
      - step_start: Agent started a new step
      - step_complete: Agent finished a step (includes data)
      - interrupt: Agent paused for human review
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
            "X-Accel-Buffering": "no",
        },
    )
