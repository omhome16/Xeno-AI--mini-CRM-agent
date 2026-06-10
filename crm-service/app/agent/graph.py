"""
Campaign Agent Graph — LangGraph workflow for AI-powered campaign creation.

This is the orchestration layer that wires together all agent nodes
into a directed graph with conditional edges and interrupt points.

Workflow:
  ┌─────────────┐
  │ parse_intent │
  └──────┬──────┘
         │
    ┌────▼─────┐
    │  router   │ → query_customers / analytics / general_chat / create_campaign
    └────┬─────┘
         │ (create_campaign path)
    ┌────▼──────────┐
    │ build_segment  │
    └────┬──────────┘
         │
    ┌────▼───────────┐
    │ review_segment  │ ← interrupt (guided mode only)
    └────┬───────────┘
         │
    ┌────▼──────────┐
    │ draft_message  │
    └────┬──────────┘
         │
    ┌────▼───────────┐
    │ review_message  │ ← interrupt (guided mode only)
    └────┬───────────┘
         │
    ┌────▼────────────┐
    │ confirm_campaign │ ← interrupt (ALWAYS)
    └────┬────────────┘
         │
    ┌────▼────────────┐
    │ execute_campaign │
    └─────────────────┘
"""

import logging
from functools import partial

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.state import CampaignState
from app.agent.llm import DualLLMClient
from app.agent import nodes

logger = logging.getLogger(__name__)


def _route_after_intent(state: CampaignState) -> str:
    """Route based on parsed intent action."""
    action = state.get("action", "general_chat")

    if action == "create_campaign":
        return "build_segment"
    elif action == "query_customers":
        return "build_segment"  # Same flow, just without message/send
    elif action == "analytics":
        return END  # Analytics queries handled directly
    else:
        return END  # General chat response


def _route_after_segment_review(state: CampaignState) -> str:
    """Route based on segment review result."""
    step = state.get("current_step", "")

    if step == "segment_edited":
        return "build_segment"  # Rebuild with new criteria
    elif step == "segment_error":
        return END  # Error — stop

    # For query_customers action, stop after showing results
    if state.get("action") == "query_customers":
        return END

    return "draft_message"


def _route_after_message_review(state: CampaignState) -> str:
    """Route based on message review result."""
    step = state.get("current_step", "")

    if step == "message_rewrite":
        return "draft_message"  # Regenerate message
    elif step == "message_error":
        return END

    return "confirm_campaign"


def _route_after_confirm(state: CampaignState) -> str:
    """Route based on campaign confirmation."""
    step = state.get("current_step", "")

    if step == "campaign_cancelled":
        return END

    return "execute_campaign"


def build_campaign_graph(llm_client: DualLLMClient) -> StateGraph:
    """
    Build the LangGraph campaign workflow.

    Args:
        llm_client: The DualLLMClient for LLM calls.

    Returns:
        Compiled LangGraph StateGraph ready for invocation.
    """
    graph = StateGraph(CampaignState)

    # ── Register nodes (bind llm_client via partial) ──
    graph.add_node("parse_intent", partial(nodes.parse_intent, llm_client=llm_client))
    graph.add_node("build_segment", partial(nodes.build_segment, llm_client=llm_client))
    graph.add_node("review_segment", nodes.review_segment)
    graph.add_node("draft_message", partial(nodes.draft_message, llm_client=llm_client))
    graph.add_node("review_message", nodes.review_message)
    graph.add_node("confirm_campaign", nodes.confirm_campaign)
    graph.add_node("execute_campaign", partial(nodes.execute_campaign, llm_client=llm_client))

    # ── Define edges ──
    graph.add_edge(START, "parse_intent")
    graph.add_conditional_edges("parse_intent", _route_after_intent)
    graph.add_edge("build_segment", "review_segment")
    graph.add_conditional_edges("review_segment", _route_after_segment_review)
    graph.add_edge("draft_message", "review_message")
    graph.add_conditional_edges("review_message", _route_after_message_review)
    graph.add_conditional_edges("confirm_campaign", _route_after_confirm)
    graph.add_edge("execute_campaign", END)

    return graph.compile(checkpointer=MemorySaver())
