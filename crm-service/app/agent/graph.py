"""
Campaign Agent Graph — LangGraph workflow for AI-powered campaign creation.

This is the orchestration layer that wires together all agent nodes
into a directed graph with conditional edges.

Campaign Studio Flows:

  ┌─────────────┐
  │ parse_intent │
  └──────┬──────┘
         │
    ┌────▼─────┐
    │  router   │
    └────┬─────┘
         │
    ┌────┴────────────┬─────────────────┬──────────────────┐
    ▼                 ▼                 ▼                  ▼
 brainstorm     query_customers    general_chat      create_campaign
    │                 │                 │                  │
 respond_       build_segment     respond_          build_segment
 brainstorm          │            general               │
    │                │                 │            draft_message
    ▼                ▼                 ▼                │
   END              END              END          execute_campaign
                                                       │
                                                      END
"""

import logging
from functools import partial

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agent.state import CampaignState
from app.agent.llm import DualLLMClient
from app.agent import nodes

logger = logging.getLogger(__name__)

# Module-level singleton — must persist across fresh/resume calls
_checkpointer = MemorySaver()


def _route_after_intent(state: CampaignState) -> str:
    """Route based on parsed intent action."""
    action = state.get("action", "general_chat")

    if action == "brainstorm":
        return "respond_brainstorm"
    elif action == "create_campaign":
        return "build_segment"
    elif action == "query_customers":
        return "build_segment"
    elif action in ("general_chat", "analytics"):
        return "respond_general"
    else:
        return "respond_general"


def _route_after_segment(state: CampaignState) -> str:
    """Route based on segment build result and original action."""
    step = state.get("current_step", "")

    if step == "segment_error":
        return END  # Error — stop

    # For query_customers action, stop after showing results
    if state.get("action") == "query_customers":
        return END

    # For create_campaign, continue to message drafting
    return "draft_message"


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
    graph.add_node("respond_brainstorm", partial(nodes.respond_brainstorm, llm_client=llm_client))
    graph.add_node("respond_general", partial(nodes.respond_general, llm_client=llm_client))
    graph.add_node("build_segment", partial(nodes.build_segment, llm_client=llm_client))
    graph.add_node("draft_message", partial(nodes.draft_message, llm_client=llm_client))
    graph.add_node("execute_campaign", partial(nodes.execute_campaign, llm_client=llm_client))

    # ── Define edges ──
    graph.add_edge(START, "parse_intent")
    graph.add_conditional_edges("parse_intent", _route_after_intent)
    graph.add_edge("respond_brainstorm", END)
    graph.add_edge("respond_general", END)
    graph.add_conditional_edges("build_segment", _route_after_segment)
    graph.add_edge("draft_message", "execute_campaign")
    graph.add_edge("execute_campaign", END)

    return graph.compile(checkpointer=_checkpointer)
