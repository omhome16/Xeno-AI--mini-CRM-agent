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
    """Route intent parsing directly to the dynamic agent reasoning loop."""
    return "agent_loop"


def _route_after_agent(state: CampaignState) -> str:
    """Route after agent reasoning: to tool execution or to final output formatter."""
    tool = state.get("tool_to_call")
    if tool:
        return "call_tool"

    # If no tools are pending, route to final formatting nodes
    action = state.get("action", "general_chat")
    mode = state.get("mode")

    if action == "brainstorm":
        return "respond_brainstorm"
    elif action == "query_customers":
        return "build_segment"
    elif action == "general_chat":
        return "respond_general"
    elif action == "create_campaign":
        if mode == "plan":
            return "draft_message"
        else:
            return "execute_campaign"
    else:
        return "respond_general"


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
    graph.add_node("agent_loop", partial(nodes.agent_loop, llm_client=llm_client))
    graph.add_node("call_tool", partial(nodes.call_tool, llm_client=llm_client))
    graph.add_node("respond_brainstorm", partial(nodes.respond_brainstorm, llm_client=llm_client))
    graph.add_node("respond_general", partial(nodes.respond_general, llm_client=llm_client))
    graph.add_node("build_segment", partial(nodes.build_segment, llm_client=llm_client))
    graph.add_node("draft_message", partial(nodes.draft_message, llm_client=llm_client))
    graph.add_node("execute_campaign", partial(nodes.execute_campaign, llm_client=llm_client))

    # ── Define edges ──
    graph.add_edge(START, "parse_intent")
    graph.add_edge("parse_intent", "agent_loop")
    
    # Dynamic loop routing from agent_loop
    graph.add_conditional_edges("agent_loop", _route_after_agent)
    
    # Loop back from tool execution
    graph.add_edge("call_tool", "agent_loop")
    
    # Terminal responses go to END
    graph.add_edge("respond_brainstorm", END)
    graph.add_edge("respond_general", END)
    graph.add_edge("build_segment", END)
    graph.add_edge("draft_message", END)
    graph.add_edge("execute_campaign", END)

    return graph.compile(checkpointer=_checkpointer)
