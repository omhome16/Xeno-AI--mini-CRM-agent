"""
Agent Nodes — Functions that execute at each step of the LangGraph workflow.

Each node receives the CampaignState, performs work, and returns
state updates. Nodes that need human review use LangGraph's
interrupt() to pause execution.

Workflow:
  parse_intent → build_segment → [review_segment] → draft_message → [review_message] → [confirm_send] → execute
  
  In guided mode: 3 interrupts (segment, message, confirmation)
  In autopilot mode: 1 interrupt (confirmation only)
"""

import json
import logging
from typing import Any

from langgraph.types import interrupt

from app.agent.state import CampaignState
from app.agent.llm import DualLLMClient
from app.agent.prompts import INTENT_PARSING_PROMPT
from app.agent import tools as agent_tools

logger = logging.getLogger(__name__)


async def parse_intent(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Parse the user's natural language message into structured intent.

    Input: state.user_message
    Output: action, audience_description, message_description, channel, offer_details
    """
    logger.info(f"Parsing intent: {state['user_message'][:100]}...")

    result = await llm_client.reason(
        system_prompt=INTENT_PARSING_PROMPT,
        user_input=state["user_message"],
    )

    # Parse JSON response
    try:
        text = result.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        intent = json.loads(text)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse intent JSON: {result[:200]}")
        intent = {
            "action": "general_chat",
            "audience_description": None,
            "message_description": None,
            "channel": "whatsapp",
            "offer_details": None,
        }

    return {
        "action": intent.get("action", "general_chat"),
        "audience_description": intent.get("audience_description", ""),
        "message_description": intent.get("message_description", ""),
        "channel": intent.get("channel", "whatsapp") or "whatsapp",
        "offer_details": intent.get("offer_details", ""),
        "current_step": "intent_parsed",
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


async def review_segment(state: CampaignState) -> dict:
    """
    Interrupt for human review of the segment (guided mode only).

    For query_customers, skip the interrupt — just show results and end.
    """
    action = state.get("action", "general_chat")
    mode = state.get("mode", "guided")

    # For pure queries, no approval needed — just pass through
    if action == "query_customers":
        return {"current_step": "segment_approved"}

    if mode == "guided":
        # Interrupt — execution pauses here until the user responds
        user_response = interrupt({
            "type": "segment_review",
            "segment_name": state.get("segment_name", ""),
            "audience_count": state.get("audience_count", 0),
            "audience_preview": state.get("audience_preview", []),
            "audience_sql": state.get("audience_sql", ""),
            "filter_criteria": state.get("filter_criteria", {}),
            "message": f"Found {state.get('audience_count', 0)} customers matching your criteria. Review the segment?",
        })

        # User can approve or provide edits
        if isinstance(user_response, dict) and user_response.get("action") == "edit":
            # User wants to change the audience — restart segment building
            return {
                "audience_description": user_response.get("new_description", state["audience_description"]),
                "current_step": "segment_edited",
            }

    return {"current_step": "segment_approved"}


async def draft_message(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Generate a channel-appropriate marketing message.

    Input: state.channel, state.audience_description, state.message_description
    Output: message_template, message_char_count
    """
    logger.info(f"Drafting {state.get('channel', 'whatsapp')} message...")

    result = await agent_tools.generate_message(
        llm_client=llm_client,
        channel=state.get("channel", "whatsapp"),
        audience_description=state.get("audience_description", ""),
        message_description=state.get("message_description", ""),
        offer_details=state.get("offer_details", ""),
    )

    return {
        "message_template": result["message_template"],
        "message_char_count": result["char_count"],
        "current_step": "message_drafted",
    }


async def review_message(state: CampaignState) -> dict:
    """
    Interrupt for human review of the drafted message (guided mode only).

    The frontend displays the message with edit capabilities:
      - Direct text editing
      - AI-assisted suggestions
    """
    mode = state.get("mode", "guided")

    if mode == "guided":
        user_response = interrupt({
            "type": "message_review",
            "message_template": state.get("message_template", ""),
            "channel": state.get("channel", "whatsapp"),
            "char_count": state.get("message_char_count", 0),
            "message": "Here's the drafted message. You can approve, edit, or request a rewrite.",
        })

        if isinstance(user_response, dict):
            if user_response.get("action") == "edit":
                return {
                    "message_template": user_response.get("new_message", state["message_template"]),
                    "message_char_count": len(user_response.get("new_message", "")),
                    "current_step": "message_edited",
                }
            elif user_response.get("action") == "rewrite":
                return {"current_step": "message_rewrite"}

    return {"current_step": "message_approved"}


async def confirm_campaign(state: CampaignState) -> dict:
    """
    Final confirmation before sending — always interrupts (both modes).

    Sending messages to real customers is irreversible, so we always
    require explicit confirmation, even in autopilot mode.
    """
    # Generate campaign name
    campaign_name = f"{state.get('segment_name', 'Campaign')} — {state.get('channel', 'whatsapp').upper()}"

    user_response = interrupt({
        "type": "campaign_confirm",
        "campaign_name": campaign_name,
        "segment_name": state.get("segment_name", ""),
        "audience_count": state.get("audience_count", 0),
        "channel": state.get("channel", "whatsapp"),
        "message_preview": state.get("message_template", "")[:200],
        "message": f"Ready to send to {state.get('audience_count', 0)} customers via {state.get('channel', 'whatsapp')}. Confirm?",
    })

    if isinstance(user_response, dict) and user_response.get("action") == "cancel":
        return {
            "error": "Campaign cancelled by user",
            "current_step": "campaign_cancelled",
        }

    return {
        "campaign_name": campaign_name,
        "current_step": "campaign_confirmed",
    }


async def execute_campaign(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Execute the campaign — create records and prepare for dispatch.

    Input: state.segment_id, state.channel, state.message_template, state.audience_sql
    Output: campaign_id, total_audience, communications_created
    """
    logger.info(f"Executing campaign: {state.get('campaign_name', 'unknown')}")

    result = await agent_tools.execute_campaign(
        llm_client=llm_client,
        segment_id=state["segment_id"],
        channel=state["channel"],
        message_template=state["message_template"],
        campaign_name=state.get("campaign_name", "Campaign"),
        audience_sql=state["audience_sql"],
    )

    if result.get("error"):
        return {
            "error": result["error"],
            "current_step": "campaign_error",
        }

    return {
        "campaign_id": result["campaign_id"],
        "total_audience": result["total_audience"],
        "communications_created": result["communications_created"],
        "current_step": "campaign_executing",
    }
