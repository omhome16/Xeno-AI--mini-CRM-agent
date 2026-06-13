"""
Chat API Router — The main AI agent interface (Campaign Studio).

Endpoints:
  POST /api/chat            — Floating copilot chat (updates parameters)
  POST /api/chat/plan       — Generate a campaign plan from a brief
  POST /api/chat/execute    — Execute an approved campaign end-to-end
  GET  /api/chat/stream/:id — SSE stream for real-time updates
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
from app.sse.manager import push_event, event_stream, get_or_create_queue
from app.agent.prompts import (
    IMPROVE_MESSAGE_PROMPT,
    AUDIENCE_RECOMMENDATION_PROMPT,
    STRATEGY_RECOMMENDATION_PROMPT,
    MESSAGE_RECOMMENDATION_PROMPT,
    COPILOT_INTENT_PROMPT,
)
from app.database import get_main_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


# ── Request/Response Models ──

class ChatRequest(BaseModel):
    """Request to start a new chat or send a message."""
    message: str = Field(..., min_length=1, max_length=2000)
    mode: str = Field(default="copilot")
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


class RecommendationAudienceResponse(BaseModel):
    name: str
    filters: dict
    count: int
    reason: str
    avg_spent: float
    avg_orders: float


class MetadataRequest(BaseModel):
    cities: list[str] = Field(default_factory=list)


class MetadataCity(BaseModel):
    city: str
    count: int


class MetadataTag(BaseModel):
    tag: str
    count: int


class MetadataResponse(BaseModel):
    cities: list[MetadataCity]
    tags: list[MetadataTag]
    max_spent: float
    max_orders: int


class StrategyRequest(BaseModel):
    filters: dict


class StrategyResponse(BaseModel):
    goal: str
    channel: str
    reason: str


class MessageRecRequest(BaseModel):
    audience_desc: str
    goal: str
    channel: str


class MessageRecResponse(BaseModel):
    type: str
    content: str
    reason: str


class CountRequest(BaseModel):
    filters: dict


class CountResponse(BaseModel):
    count: int


# ── Background task: Run the graph ──

async def _run_graph(
    conversation_id: str,
    state: CampaignState,
    llm_client: DualLLMClient,
) -> None:
    """
    Run the LangGraph workflow as a background task.

    Streams events to the SSE queue as the graph progresses.
    """
    try:
        graph = build_campaign_graph(llm_client)

        logger.info(f"[_run_graph] Starting graph execution for conversation_id={conversation_id}")
        await push_event(conversation_id, "step_start", {
            "step": "Starting",
            "message": f"Processing campaign plan...",
        })

        config = {"configurable": {"thread_id": conversation_id}}

        async for event in graph.astream(state, config=config):
            await _process_graph_event(conversation_id, event)

        # Graph completed — send result
        snapshot = await graph.aget_state(config)
        final_state = snapshot.values if snapshot else {}
        logger.info(f"[_run_graph] Graph execution completed successfully for conversation_id={conversation_id}")
        await push_event(conversation_id, "result", {
            "step": "complete",
            "state": _serialize_state(final_state),
        })

    except Exception as e:
        logger.error(f"[_run_graph] Graph execution error for conversation_id={conversation_id}: {e}", exc_info=True)
        await push_event(conversation_id, "error", {
            "message": f"Agent error: {str(e)[:300]}",
        })


async def _run_copilot(
    conversation_id: str,
    message: str,
    history: list[dict],
    brief: dict,
    llm_client: DualLLMClient,
) -> None:
    """
    Run the AI copilot to generate responses and parse form updates.
    """
    try:
        logger.info(f"[_run_copilot] Starting copilot logic for conversation_id={conversation_id}")
        await push_event(conversation_id, "step_start", {
            "step": "Copilot",
            "message": "AI Copilot is thinking...",
        })

        # Build history context
        history_parts = []
        for msg in history[-6:]:
            role = msg.get("role") or "user"
            content = msg.get("content", "").strip()
            if content:
                history_parts.append(f"{role}: {content}")
        history_ctx = "\n".join(history_parts)

        user_input = ""
        if history_ctx:
            user_input += f"Conversation history:\n{history_ctx}\n\n"
        user_input += f"User message: {message}"

        system_prompt = COPILOT_INTENT_PROMPT.format(
            current_fields=json.dumps(brief, indent=2)
        )

        raw = await llm_client.reason(system_prompt=system_prompt, user_input=user_input)
        from app.agent.nodes import _parse_json_response
        parsed = _parse_json_response(raw)

        reply = parsed.get("reply") or "I'm here to help."
        field_updates = parsed.get("field_updates") or {}
        trigger_launch = bool(parsed.get("trigger_launch", False))

        await push_event(conversation_id, "result", {
            "step": "complete",
            "state": {
                "ai_response": reply,
                "field_updates": field_updates,
                "trigger_launch": trigger_launch,
                "suggestions": []
            }
        })
    except Exception as e:
        logger.error(f"[_run_copilot] Copilot execution error: {e}", exc_info=True)
        await push_event(conversation_id, "error", {
            "message": f"Copilot error: {str(e)[:300]}",
        })


async def _run_oneshot_copilot(
    conversation_id: str,
    message: str,
    history: list[dict],
    brief: dict,
    llm_client: DualLLMClient,
) -> None:
    """
    Run the AI copilot in one-shot mode to extract campaign parameters, check for missing fields,
    and trigger campaign execution when ready.
    """
    try:
        logger.info(f"[_run_oneshot_copilot] Starting oneshot copilot for conversation_id={conversation_id}")
        await push_event(conversation_id, "step_start", {
            "step": "Copilot",
            "message": "AI Copilot is analyzing campaign parameters...",
        })

        # Fetch available metadata context (distinct cities and tags) to pass to the LLM
        pool = get_main_pool()
        try:
            async with pool.acquire() as conn:
                city_rows = await conn.fetch("SELECT distinct city FROM customers WHERE city IS NOT NULL AND city != ''")
                tag_rows = await conn.fetch("SELECT distinct unnest(tags) as tag FROM customers")
            cities = [r["city"] for r in city_rows]
            tags = [r["tag"] for r in tag_rows]
            metadata_ctx = f"Available Cities: {cities}\nAvailable Tags: {tags}"
        except Exception as meta_err:
            logger.warning(f"Failed to fetch metadata for oneshot copilot context: {meta_err}")
            metadata_ctx = "Available Cities: ['Delhi', 'Bangalore', 'Mumbai']\nAvailable Tags: ['lapsed', 'vip', 'high_value', 'active']"

        # Build history context
        history_parts = []
        for msg in history[-6:]:
            role = msg.get("role") or "user"
            content = msg.get("content", "").strip()
            if content:
                history_parts.append(f"{role}: {content}")
        history_ctx = "\n".join(history_parts)

        user_input = ""
        if history_ctx:
            user_input += f"Conversation history:\n{history_ctx}\n\n"
        user_input += f"User message: {message}"

        from app.agent.prompts import ONESHOT_COPILOT_PROMPT
        system_prompt = ONESHOT_COPILOT_PROMPT.format(
            metadata=metadata_ctx,
            current_fields=json.dumps(brief, indent=2)
        )

        raw = await llm_client.reason(system_prompt=system_prompt, user_input=user_input)
        from app.agent.nodes import _parse_json_response
        parsed = _parse_json_response(raw)

        reply = parsed.get("reply") or "Processing."
        extracted_brief = parsed.get("extracted_brief") or {}
        missing_fields = parsed.get("missing_fields") or []
        trigger_launch = bool(parsed.get("trigger_launch", False))

        await push_event(conversation_id, "result", {
            "step": "complete",
            "state": {
                "ai_response": reply,
                "field_updates": extracted_brief,
                "missing_fields": missing_fields,
                "trigger_launch": trigger_launch,
                "suggestions": []
            }
        })
    except Exception as e:
        logger.error(f"[_run_oneshot_copilot] Oneshot copilot error: {e}", exc_info=True)
        await push_event(conversation_id, "error", {
            "message": f"Copilot error: {str(e)[:300]}",
        })


async def _process_graph_event(conversation_id: str, event: dict) -> None:
    """Process a single graph stream event and push to SSE."""
    for node_name, node_output in event.items():
        # Normal node completion
        logger.info(f"[_process_graph_event] Node '{node_name}' completed.")
        
        step_name = node_name
        if node_name == "call_tool" and isinstance(node_output, dict):
            step_name = node_output.get("current_step", node_name)
        elif node_name == "setup_campaign_state":
            step_name = "setup_state"

        await push_event(conversation_id, "step_complete", {
            "step": step_name,
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
    summary="Chat with the AI Copilot to update fields or ask questions",
)
async def start_chat(request: ChatRequest):
    """
    Send a message to the AI Copilot.
    """
    settings = get_settings()
    conversation_id = request.conversation_id or uuid4().hex
    get_or_create_queue(conversation_id)

    llm_client = DualLLMClient(
        gemini_key=settings.GEMINI_API_KEY,
    )

    if not llm_client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Gemini is not configured. Set GEMINI_API_KEY in .env.",
        )

    if request.mode == "oneshot":
        asyncio.create_task(
            _run_oneshot_copilot(conversation_id, request.message, request.history, request.brief, llm_client),
            name=f"oneshot-{conversation_id[:8]}",
        )
    else:
        asyncio.create_task(
            _run_copilot(conversation_id, request.message, request.history, request.brief, llm_client),
            name=f"copilot-{conversation_id[:8]}",
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
    """
    settings = get_settings()
    conversation_id = request.conversation_id or uuid4().hex
    get_or_create_queue(conversation_id)

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
        "action": "create_campaign",
        "audience_description": audience,
        "message_description": message_idea or offer or f"Campaign message for {audience}",
        "channel": channel,
        "offer_details": offer,
        "current_step": "planning",
    }

    llm_client = DualLLMClient(
        gemini_key=settings.GEMINI_API_KEY,
    )

    if not llm_client.is_configured:
        raise HTTPException(status_code=503, detail="Gemini is not configured. Set GEMINI_API_KEY in .env.")

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
    Execute a fully approved campaign:
    compile segment SQL -> draft message -> launch campaign.
    """
    settings = get_settings()
    conversation_id = request.conversation_id or uuid4().hex
    get_or_create_queue(conversation_id)

    state: CampaignState = {
        "user_message": f"Execute campaign: {request.audience_description}",
        "mode": "execute",
        "conversation_id": conversation_id,
        "action": "create_campaign",
        "audience_description": request.audience_description,
        "message_description": request.message_description or request.brief.get("message_idea", ""),
        "channel": request.channel,
        "offer_details": request.offer_details or request.brief.get("offer", ""),
        "message_template": request.message_template if request.message_template else None,
        "brief": request.brief,
        "current_step": "executing",
    }

    llm_client = DualLLMClient(
        gemini_key=settings.GEMINI_API_KEY,
    )

    if not llm_client.is_configured:
        raise HTTPException(status_code=503, detail="Gemini is not configured. Set GEMINI_API_KEY in .env.")

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
    )

    if not llm_client.is_configured:
        raise HTTPException(
            status_code=503,
            detail="Gemini is not configured. Set GEMINI_API_KEY in .env.",
        )

    prompt = IMPROVE_MESSAGE_PROMPT.format(
        message_template=request.message_template.replace("{", "{{").replace("}", "}}"),
        instruction=request.instruction,
        channel=request.channel,
    )

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


@router.get(
    "/stream/{conversation_id}",
    summary="SSE stream for real-time updates",
)
async def chat_stream(conversation_id: str):
    """
    Server-Sent Events stream for a conversation.
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


@router.post(
    "/recommendations/audience",
    response_model=list[RecommendationAudienceResponse],
    summary="Get recommended audience segments based on database analytics"
)
async def recommend_audience():
    settings = get_settings()
    llm_client = DualLLMClient(gemini_key=settings.GEMINI_API_KEY)
    if not llm_client.is_configured:
        raise HTTPException(status_code=503, detail="Gemini is not configured.")
        
    pool = get_main_pool()
    try:
        async with pool.acquire() as conn:
            total = await conn.fetchval("SELECT COUNT(*) FROM customers")
            cities = await conn.fetch("SELECT city, COUNT(*) as count FROM customers WHERE city IS NOT NULL GROUP BY city ORDER BY count DESC LIMIT 5")
            tags = await conn.fetch("SELECT unnest(tags) as tag, COUNT(*) as count FROM customers GROUP BY tag ORDER BY count DESC LIMIT 10")
            spend = await conn.fetchrow("SELECT MIN(total_spent) as min, MAX(total_spent) as max, AVG(total_spent) as avg FROM customers")
            
        stats_ctx = f"Total Customers: {total}\n"
        stats_ctx += "Top Cities:\n"
        for r in cities:
            stats_ctx += f"  - {r['city']}: {r['count']}\n"
        stats_ctx += "Tags:\n"
        for r in tags:
            stats_ctx += f"  - {r['tag']}: {r['count']}\n"
        stats_ctx += f"Spend Statistics:\n  - Min: {spend['min']}\n  - Max: {spend['max']}\n  - Avg: {spend['avg']:.2f}\n"
        
        system_prompt = AUDIENCE_RECOMMENDATION_PROMPT.replace("{stats}", stats_ctx)
        
        raw = await llm_client.reason(
            system_prompt=system_prompt,
            user_input="Suggest 2-3 target segments with reasons."
        )
        from app.agent.nodes import _parse_json_response
        recs = _parse_json_response(raw)
        
        if not isinstance(recs, list):
            if isinstance(recs, dict):
                for k, v in recs.items():
                    if isinstance(v, list):
                        recs = v
                        break
            if not isinstance(recs, list):
                raise ValueError("LLM did not return a list")
                
        async def fetch_segment_stats(flts):
            conditions = []
            params = []
            idx = 1
            
            cities_list = flts.get("cities")
            if cities_list:
                cleaned_cities = [c for c in cities_list if str(c).strip().lower() not in {"all", "any", "none", "null", "", "any city", "all cities"}]
                if cleaned_cities:
                    conditions.append(f"city = ANY(${idx}::text[])")
                    params.append(list(cleaned_cities))
                    idx += 1
                
            tags_list = flts.get("tags")
            if tags_list:
                cleaned_tags = [t for t in tags_list if str(t).strip().lower() not in {"all", "any", "none", "null", "", "any tag", "all tags"}]
                if cleaned_tags:
                    conditions.append(f"tags @> ${idx}::text[]")
                    params.append(list(cleaned_tags))
                    idx += 1
                
            min_spent = flts.get("min_spent")
            if min_spent is not None:
                conditions.append(f"total_spent >= ${idx}")
                params.append(float(min_spent))
                idx += 1
                
            min_orders = flts.get("min_orders")
            if min_orders is not None:
                conditions.append(f"total_orders >= ${idx}")
                params.append(int(min_orders))
                idx += 1
                
            where_clause = " AND ".join(conditions) if conditions else "TRUE"
            query = f"SELECT COUNT(*) as count, COALESCE(AVG(total_spent), 0) as avg_spent, COALESCE(AVG(total_orders), 0) as avg_orders FROM customers WHERE {where_clause}"
            
            async with pool.acquire() as conn:
                row = await conn.fetchrow(query, *params)
                return row["count"], float(row["avg_spent"]), float(row["avg_orders"])

        final_recs = []
        for rec in recs:
            filters = rec.get("filters", {})
            # Clean filters in-place to send clean JSON filters back to the frontend
            if "cities" in filters and filters["cities"]:
                cleaned_cities = [c for c in filters["cities"] if str(c).strip().lower() not in {"all", "any", "none", "null", "", "any city", "all cities"}]
                if cleaned_cities:
                    filters["cities"] = cleaned_cities
                else:
                    filters.pop("cities", None)
            
            if "tags" in filters and filters["tags"]:
                cleaned_tags = [t for t in filters["tags"] if str(t).strip().lower() not in {"all", "any", "none", "null", "", "any tag", "all tags"}]
                if cleaned_tags:
                    filters["tags"] = cleaned_tags
                else:
                    filters.pop("tags", None)
            
            try:
                real_count, avg_spent, avg_orders = await fetch_segment_stats(filters)
            except Exception as query_err:
                logger.warning(f"Failed to query count for filter {filters}: {query_err}")
                real_count = rec.get("count") or 0
                avg_spent = 0.0
                avg_orders = 0.0
            
            if real_count > 0:
                final_recs.append({
                    "name": rec.get("name", "Target Segment"),
                    "filters": filters,
                    "count": real_count,
                    "reason": rec.get("reason", ""),
                    "avg_spent": avg_spent,
                    "avg_orders": avg_orders
                })

        FALLBACK_SEGMENTS = [
            {
                "name": "VIP Spenders",
                "filters": {"tags": ["vip"]},
                "reason": "High-value customers with premium brand affinity and top spending history."
            },
            {
                "name": "Lapsed Customers",
                "filters": {"tags": ["lapsed"]},
                "reason": "Customers who haven't ordered recently but have historical engagement."
            },
            {
                "name": "Active Regulars",
                "filters": {"tags": ["regular"]},
                "reason": "Frequent buyers who maintain steady interactions with the brand."
            }
        ]
        
        for fallback in FALLBACK_SEGMENTS:
            if len(final_recs) >= 3:
                break
            # Check if this fallback is already represented (by filters or name)
            already_exists = any(
                fr["name"].lower() == fallback["name"].lower() or 
                fr["filters"] == fallback["filters"] 
                for fr in final_recs
            )
            if not already_exists:
                try:
                    real_count, avg_spent, avg_orders = await fetch_segment_stats(fallback["filters"])
                    if real_count > 0:
                        final_recs.append({
                            "name": fallback["name"],
                            "filters": fallback["filters"],
                            "count": real_count,
                            "reason": fallback["reason"],
                            "avg_spent": avg_spent,
                            "avg_orders": avg_orders
                        })
                except Exception as fb_err:
                    logger.warning(f"Failed to fetch stats for fallback segment {fallback['name']}: {fb_err}")
                    
        return final_recs
        
    except Exception as e:
        logger.error(f"Failed to get audience recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to suggest segments: {str(e)}")


@router.post(
    "/recommendations/campaigns",
    response_model=list[dict],
    summary="Get recommended campaign prompts based on database analytics and brand profile"
)
async def recommend_campaigns():
    settings = get_settings()
    llm_client = DualLLMClient(gemini_key=settings.GEMINI_API_KEY)
    if not llm_client.is_configured:
        raise HTTPException(status_code=503, detail="Gemini is not configured.")
        
    pool = get_main_pool()
    try:
        async with pool.acquire() as conn:
            # 1. Total customers
            total = await conn.fetchval("SELECT COUNT(*) FROM customers")
            
            # 2. Top Cities
            cities = await conn.fetch("SELECT city, COUNT(*) as count FROM customers WHERE city IS NOT NULL AND city != '' GROUP BY city ORDER BY count DESC LIMIT 5")
            
            # 3. Tags
            tags = await conn.fetch("SELECT unnest(tags) as tag, COUNT(*) as count FROM customers GROUP BY tag ORDER BY count DESC LIMIT 10")
            
            # 4. Brand profile catalogs
            brand_profile_row = await conn.fetchrow("SELECT data FROM brand_profile ORDER BY id DESC LIMIT 1")
            brand_catalog = []
            if brand_profile_row:
                bp_data = brand_profile_row["data"]
                if isinstance(bp_data, str):
                    bp_data = json.loads(bp_data)
                brand_catalog = bp_data.get("product_catalog", [])

        stats_ctx = f"Total Customers: {total}\n"
        stats_ctx += "Top Cities:\n"
        for r in cities:
            stats_ctx += f"  - {r['city']}: {r['count']}\n"
        stats_ctx += "Tags:\n"
        for r in tags:
            stats_ctx += f"  - {r['tag']}: {r['count']}\n"
        if brand_catalog:
            stats_ctx += "Brand Products Catalogs:\n"
            for p in brand_catalog[:5]:
                stats_ctx += f"  - {p.get('name')} (Price: {p.get('price')}, Category: {p.get('category')})\n"
        
        from app.agent.prompts import CAMPAIGN_RECOMMENDATION_PROMPT
        system_prompt = CAMPAIGN_RECOMMENDATION_PROMPT.format(stats=stats_ctx)
        
        raw = await llm_client.reason(
            system_prompt=system_prompt,
            user_input="Suggest 3 high-impact campaign prompts."
        )
        from app.agent.nodes import _parse_json_response
        recs = _parse_json_response(raw)
        
        if not isinstance(recs, list):
            if isinstance(recs, dict):
                for k, v in recs.items():
                    if isinstance(v, list):
                        recs = v
                        break
            if not isinstance(recs, list):
                raise ValueError("LLM did not return a list")
                
        return recs
        
    except Exception as e:
        logger.error(f"Failed to get campaign recommendations: {e}", exc_info=True)
        # Return logical fallback suggestions in case of failure so the app doesn't break
        return [
            {
                "prompt": "Run a campaign for lapsed customers in Delhi offering a 20% discount using SMS",
                "description": "Targets lapsed customers in Delhi to win them back.",
                "channel": "sms",
                "audience_desc": "lapsed customers in Delhi",
                "offer": "20% discount"
            },
            {
                "prompt": "Launch a campaign for VIP customers in Bangalore offering free shipping using whatsapp",
                "description": "Rewards VIP customers in Bangalore with free shipping.",
                "channel": "whatsapp",
                "audience_desc": "VIP customers in Bangalore",
                "offer": "free shipping"
            },
            {
                "prompt": "Launch a campaign for high value customers in Delhi offering free shipping using whatsapp",
                "description": "Promotes free shipping to high-value customers in Delhi.",
                "channel": "whatsapp",
                "audience_desc": "high value customers in Delhi",
                "offer": "free shipping"
            }
        ]


@router.post(
    "/recommendations/strategy",
    response_model=StrategyResponse,
    summary="Get goal and channel recommendation for specific filters"
)
async def recommend_strategy(request: StrategyRequest):
    settings = get_settings()
    llm_client = DualLLMClient(gemini_key=settings.GEMINI_API_KEY)
    if not llm_client.is_configured:
        raise HTTPException(status_code=503, detail="Gemini is not configured. Set GEMINI_API_KEY in .env.")
        
    try:
        import json
        system_prompt = STRATEGY_RECOMMENDATION_PROMPT.replace(
            "{filters}", json.dumps(request.filters, indent=2)
        )
        raw = await llm_client.reason(
            system_prompt=system_prompt,
            user_input="Recommend Goal and Channel."
        )
        from app.agent.nodes import _parse_json_response
        res = _parse_json_response(raw)
        return StrategyResponse(
            goal=res.get("goal", "Re-engage lapsed customers"),
            channel=res.get("channel", "whatsapp"),
            reason=res.get("reason", "")
        )
    except Exception as e:
        logger.error(f"Failed to get strategy recommendation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Strategy recommendation failed: {str(e)}")


@router.post(
    "/recommendations/message",
    response_model=list[MessageRecResponse],
    summary="Get message template options (Casual, Urgent, Formal) based on context"
)
async def recommend_message(request: MessageRecRequest):
    settings = get_settings()
    llm_client = DualLLMClient(gemini_key=settings.GEMINI_API_KEY)
    if not llm_client.is_configured:
        raise HTTPException(status_code=503, detail="Gemini is not configured. Set GEMINI_API_KEY in .env.")
        
    from app.services.brand_service import fetch_brand_profile_ctx as _fetch_brand_profile_ctx
    brand_profile = await _fetch_brand_profile_ctx()
    
    try:
        system_prompt = (
            MESSAGE_RECOMMENDATION_PROMPT
            .replace("{audience_desc}", request.audience_desc)
            .replace("{goal}", request.goal)
            .replace("{channel}", request.channel)
            .replace("{brand_profile}", brand_profile)
        )
        raw = await llm_client.reason(
            system_prompt=system_prompt,
            user_input="Generate 3 copy variations with reasons."
        )
        from app.agent.nodes import _parse_json_response
        res = _parse_json_response(raw)
        if not isinstance(res, list):
            raise ValueError("LLM did not return a list")
        return [
            MessageRecResponse(
                type=item.get("type", "Casual"),
                content=item.get("content", ""),
                reason=item.get("reason", "")
            )
            for item in res
        ]
    except Exception as e:
        logger.error(f"Failed to get message recommendations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Message recommendation failed: {str(e)}")


@router.post(
    "/count",
    response_model=CountResponse,
    summary="Get exact customer count for segment filters"
)
async def get_segment_count(request: CountRequest):
    pool = get_main_pool()
    filters = request.filters
    try:
        conditions = []
        params = []
        idx = 1
        
        cities_list = filters.get("cities")
        if cities_list:
            conditions.append(f"city = ANY(${idx}::text[])")
            params.append(list(cities_list))
            idx += 1
            
        tags_list = filters.get("tags")
        if tags_list:
            conditions.append(f"tags @> ${idx}::text[]")
            params.append(list(tags_list))
            idx += 1
            
        min_spent = filters.get("min_spent")
        if min_spent is not None and min_spent != "":
            conditions.append(f"total_spent >= ${idx}")
            params.append(float(min_spent))
            idx += 1

        max_spent = filters.get("max_spent")
        if max_spent is not None and max_spent != "":
            conditions.append(f"total_spent <= ${idx}")
            params.append(float(max_spent))
            idx += 1
            
        min_orders = filters.get("min_orders")
        if min_orders is not None and min_orders != "":
            conditions.append(f"total_orders >= ${idx}")
            params.append(int(min_orders))
            idx += 1

        max_orders = filters.get("max_orders")
        if max_orders is not None and max_orders != "":
            conditions.append(f"total_orders <= ${idx}")
            params.append(int(max_orders))
            idx += 1
            
        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        query = f"SELECT COUNT(*) FROM customers WHERE {where_clause}"
        
        async with pool.acquire() as conn:
            count = await conn.fetchval(query, *params)
        return CountResponse(count=count)
    except Exception as e:
        logger.error(f"Failed to get segment count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/metadata",
    response_model=MetadataResponse,
    summary="Get dynamic campaign metadata filters (distinct cities, tag counts, spend limits) from the database"
)
async def get_metadata(request: MetadataRequest):
    pool = get_main_pool()
    try:
        async with pool.acquire() as conn:
            city_rows = await conn.fetch(
                "SELECT city, COUNT(*) as count FROM customers WHERE city IS NOT NULL AND city != '' GROUP BY city ORDER BY count DESC"
            )
            
            limits = await conn.fetchrow(
                "SELECT COALESCE(MAX(total_spent), 0) as max_spent, COALESCE(MAX(total_orders), 0) as max_orders FROM customers"
            )
            max_spent = float(limits["max_spent"])
            max_orders = int(limits["max_orders"])
            
            if request.cities:
                tag_rows = await conn.fetch(
                    "SELECT unnest(tags) as tag, COUNT(*) as count FROM customers WHERE city = ANY($1::text[]) GROUP BY tag ORDER BY count DESC",
                    request.cities
                )
            else:
                tag_rows = await conn.fetch(
                    "SELECT unnest(tags) as tag, COUNT(*) as count FROM customers GROUP BY tag ORDER BY count DESC"
                )
                
        cities = [{"city": r["city"], "count": r["count"]} for r in city_rows]
        tags = [{"tag": r["tag"], "count": r["count"]} for r in tag_rows]
        
        return MetadataResponse(
            cities=cities,
            tags=tags,
            max_spent=max_spent,
            max_orders=max_orders
        )
    except Exception as e:
        logger.error(f"Failed to query metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
