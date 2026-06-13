"""
Campaign Agent Graph — LangGraph workflow for AI-powered campaign creation.

Architecture:
   START ──► setup_campaign_state ──► agent_loop ◄───► call_tool
                                          │ (tool_to_call == null)
                                          ▼
                                         END
"""

import logging
from functools import partial

from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from redis.asyncio import Redis as AsyncRedis
from app.config import get_settings
from langgraph.graph import END, START, StateGraph

from app.agent import nodes
from app.agent.llm import DualLLMClient
from app.agent.state import CampaignState

logger = logging.getLogger(__name__)

_checkpointer = None

def get_checkpointer() -> AsyncRedisSaver:
    global _checkpointer
    if _checkpointer is None:
        settings = get_settings()
        _checkpointer = AsyncRedisSaver(settings.REDIS_URL)
    return _checkpointer


def _route_after_agent(state: CampaignState) -> str:
    """
    Route after each agent_loop iteration.

    If the agent decided to call a tool (tool_to_call is set), execute it via
    call_tool and loop back to agent_loop afterward. Otherwise, the agent has
    produced its final response for this turn — end the graph run.
    """
    if state.get("tool_to_call"):
        return "call_tool"
    return END


def build_campaign_graph(llm_client: DualLLMClient) -> StateGraph:
    """
    Build and compile the LangGraph campaign workflow.

    Args:
        llm_client: The DualLLMClient for all LLM calls.

    Returns:
        Compiled LangGraph graph, checkpointed with MemorySaver.
    """
    graph = StateGraph(CampaignState)

    # ── Register nodes ──────────────────────────────────────────────────────────
    graph.add_node("setup_campaign_state", partial(nodes.setup_campaign_state, llm_client=llm_client))
    graph.add_node("agent_loop", partial(nodes.agent_loop, llm_client=llm_client))
    graph.add_node("call_tool", partial(nodes.call_tool, llm_client=llm_client))

    # ── Define edges ───────────────────────────────────────────────────────────
    graph.add_edge(START, "setup_campaign_state")
    graph.add_edge("setup_campaign_state", "agent_loop")

    # Main reasoning loop: agent_loop ↔ call_tool, exits to END when done
    graph.add_conditional_edges(
        "agent_loop",
        _route_after_agent,
        {"call_tool": "call_tool", END: END},
    )
    graph.add_edge("call_tool", "agent_loop")

    return graph.compile(checkpointer=get_checkpointer())