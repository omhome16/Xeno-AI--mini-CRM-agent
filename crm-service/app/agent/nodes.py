"""
Agent Nodes — Functions that execute at each step of the LangGraph workflow.

Each node receives the CampaignState, performs work, and returns
state updates. Nodes that need human review use LangGraph's
interrupt() to pause execution.

Workflow (Campaign Studio):
  Brainstorm:  parse_intent → respond_brainstorm → END
  Query:       parse_intent → build_segment → END
  General:     parse_intent → respond_general → END
  Execute:     parse_intent → build_segment → draft_message → execute_campaign → END
"""

import json
import logging
from typing import Any

from langgraph.types import interrupt

from app.agent.state import CampaignState
from app.agent.llm import DualLLMClient
from app.agent.prompts import (
    INTENT_PARSING_PROMPT,
    BRAINSTORM_PROMPT,
    GENERAL_RESPONSE_PROMPT,
)
from app.agent import tools as agent_tools

logger = logging.getLogger(__name__)


def _parse_json_response(text: str) -> dict:
    """Parse a JSON response from an LLM, handling code fences."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse JSON: {text[:200]}")
        return {}


async def parse_intent(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Parse the user's natural language message into structured intent.

    Input: state.user_message, state.messages (conversation history)
    Output: action, audience_description, message_description, channel, offer_details, brief_updates
    """
    logger.info(f"Parsing intent: {state['user_message'][:100]}...")

    # Build context from conversation history
    history = state.get("messages", [])
    context_parts = []
    for msg in history[-6:]:  # Last 6 messages for context
        role = msg.get("role", msg.get("type", "user"))
        content = msg.get("content", "")
        if content:
            context_parts.append(f"{role}: {content}")

    # Include current brief context
    brief = state.get("brief", {})
    brief_context = ""
    if brief:
        brief_context = f"\n\nCurrent campaign brief: {json.dumps(brief)}"

    user_input = state["user_message"]
    if context_parts:
        user_input = (
            "Previous conversation:\n"
            + "\n".join(context_parts)
            + brief_context
            + f"\n\nCurrent message: {state['user_message']}"
        )
    elif brief_context:
        user_input = brief_context + f"\n\nCurrent message: {state['user_message']}"

    result = await llm_client.reason(
        system_prompt=INTENT_PARSING_PROMPT,
        user_input=user_input,
    )

    intent = _parse_json_response(result)
    if not intent:
        intent = {
            "action": "general_chat",
            "audience_description": None,
            "message_description": None,
            "channel": None,
            "offer_details": None,
            "brief_updates": {},
        }

    return {
        "action": intent.get("action", "general_chat"),
        "audience_description": intent.get("audience_description", ""),
        "message_description": intent.get("message_description", ""),
        "channel": intent.get("channel", "") or "",
        "offer_details": intent.get("offer_details", ""),
        "brief_updates": intent.get("brief_updates", {}),
        "current_step": "intent_parsed",
    }


async def respond_brainstorm(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Generate a conversational brainstorm response with structured suggestions.

    Input: state.user_message, state.brief, state.messages
    Output: ai_response, suggestions, brief_updates, ready_to_plan
    """
    from app.sse.manager import push_event
    conv_id = state.get("conversation_id", "")

    await push_event(conv_id, "step_start", {
        "step": "Thinking",
        "message": "Brainstorming campaign ideas...",
    })

    # Merge any brief_updates from intent parsing into brief
    brief = dict(state.get("brief", {}))
    updates_from_intent = state.get("brief_updates", {})
    if updates_from_intent:
        for k, v in updates_from_intent.items():
            if v:
                brief[k] = v

    # Format brief for prompt
    brief_text = json.dumps(brief, indent=2) if brief else "Empty — no decisions made yet"

    prompt = BRAINSTORM_PROMPT.replace("{brief}", brief_text)

    # Build conversation context
    history = state.get("messages", [])
    context_parts = []
    for msg in history[-8:]:
        role = msg.get("role", msg.get("type", "user"))
        content = msg.get("content", "")
        if content:
            context_parts.append(f"{role}: {content}")

    user_input = state["user_message"]
    if context_parts:
        user_input = (
            "Conversation so far:\n"
            + "\n".join(context_parts)
            + f"\n\nLatest message from marketer: {state['user_message']}"
        )

    result = await llm_client.reason(
        system_prompt=prompt,
        user_input=user_input,
    )

    parsed = _parse_json_response(result)

    # Extract structured data
    ai_response = parsed.get("response", result if not parsed else "Let me help you plan a campaign!")
    suggestions = parsed.get("suggestions", [])
    new_brief_updates = parsed.get("brief_updates", {})
    ready_to_plan = parsed.get("ready_to_plan", False)

    # Merge new updates into brief
    if new_brief_updates:
        for k, v in new_brief_updates.items():
            if v:
                brief[k] = v

    return {
        "ai_response": ai_response,
        "suggestions": suggestions,
        "brief": brief,
        "brief_updates": new_brief_updates,
        "ready_to_plan": ready_to_plan,
        "current_step": "brainstorm_responded",
    }


async def respond_general(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Generate a response for general chat or analytics questions.

    Input: state.user_message
    Output: ai_response
    """
    result = await llm_client.generate(
        system_prompt=GENERAL_RESPONSE_PROMPT,
        user_input=state["user_message"],
    )

    parsed = _parse_json_response(result)
    ai_response = parsed.get("response", result if not parsed else "I'm here to help with your CRM campaigns!")

    return {
        "ai_response": ai_response,
        "current_step": "general_responded",
    }


async def build_segment(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Query the database to find matching customers and create a segment.

    Input: state.audience_description
    Output: audience_sql, audience_count, audience_preview, segment_id, segment_name
    """
    from app.sse.manager import push_event

    conv_id = state.get("conversation_id", "")
    logger.info(f"Building segment for: {state.get('audience_description', '')[:100]}")

    await push_event(conv_id, "step_start", {
        "step": "Generating SQL query",
        "message": f"Translating \"{state.get('audience_description', '')[:80]}\" to SQL...",
    })

    # Query customers via AI SQL
    query_result = await agent_tools.query_customers(
        llm_client, state["audience_description"]
    )

    if query_result.get("error"):
        return {
            "error": query_result["error"],
            "current_step": "segment_error",
        }

    # Push SQL thinking to frontend
    await push_event(conv_id, "step_start", {
        "step": "SQL executed",
        "message": f"Query: {query_result.get('sql', '')[:120]}",
    })

    if query_result["count"] == 0:
        return {
            "error": "No customers match this criteria. Try a broader description.",
            "current_step": "segment_error",
        }

    await push_event(conv_id, "step_start", {
        "step": f"Found {query_result['count']} customers",
        "message": f"Building segment with {query_result['count']} matching customers...",
    })

    # Create and save segment
    segment_result = await agent_tools.create_segment(
        llm_client=llm_client,
        audience_description=state["audience_description"],
        customer_count=query_result["count"],
    )

    return {
        "audience_sql": query_result["sql"],
        "audience_count": query_result["count"],
        "audience_preview": query_result["results"],
        "segment_id": segment_result["segment_id"],
        "segment_name": segment_result["name"],
        "filter_criteria": segment_result["filter_criteria"],
        "current_step": "segment_built",
    }


async def draft_message(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Generate a channel-appropriate marketing message.

    Input: state.channel, state.audience_description, state.message_description
    Output: message_template, message_char_count
    """
    from app.sse.manager import push_event
    conv_id = state.get("conversation_id", "")

    channel = state.get("channel", "whatsapp") or "whatsapp"
    logger.info(f"Drafting {channel} message...")

    await push_event(conv_id, "step_start", {
        "step": f"Drafting {channel.upper()} message",
        "message": f"Generating personalized message for {state.get('audience_description', 'target audience')[:60]}...",
    })

    result = await agent_tools.generate_message(
        llm_client=llm_client,
        channel=channel,
        audience_description=state.get("audience_description", ""),
        message_description=state.get("message_description", ""),
        offer_details=state.get("offer_details", ""),
    )

    return {
        "message_template": result["message_template"],
        "message_char_count": result["char_count"],
        "current_step": "message_drafted",
    }


async def execute_campaign(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Execute the campaign — create records and prepare for dispatch.

    Input: state.segment_id, state.channel, state.message_template, state.audience_sql
    Output: campaign_id, total_audience, communications_created
    """
    from app.sse.manager import push_event
    conv_id = state.get("conversation_id", "")

    # Generate campaign name
    campaign_name = f"{state.get('segment_name', 'Campaign')} — {(state.get('channel', 'whatsapp') or 'whatsapp').upper()}"

    logger.info(f"Executing campaign: {campaign_name}")

    await push_event(conv_id, "step_start", {
        "step": "Creating campaign",
        "message": f"Launching \"{campaign_name}\" to {state.get('audience_count', 0)} customers...",
    })

    result = await agent_tools.execute_campaign(
        llm_client=llm_client,
        segment_id=state["segment_id"],
        channel=state.get("channel", "whatsapp") or "whatsapp",
        message_template=state["message_template"],
        campaign_name=campaign_name,
        audience_sql=state["audience_sql"],
    )

    if result.get("error"):
        return {
            "error": result["error"],
            "current_step": "campaign_error",
        }

    return {
        "campaign_id": result["campaign_id"],
        "campaign_name": campaign_name,
        "total_audience": result["total_audience"],
        "communications_created": result["communications_created"],
        "current_step": "campaign_executing",
    }
