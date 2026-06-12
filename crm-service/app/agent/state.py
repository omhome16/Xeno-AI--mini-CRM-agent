"""
Agent State — TypedDict defining the state that flows through the LangGraph workflow.

Design principles:
  - Fields are populated progressively as the workflow advances.
  - Per-turn scratch fields (think_pad, tool_to_call, etc.) are reset at the start
    of each turn by parse_intent, so stale values never pollute the next turn.
  - brand_profile_ctx is fetched once per turn in parse_intent and cached here
    so downstream nodes (agent_loop, call_tool) never hit the DB redundantly.
"""

from typing import Any, Dict, List, Optional, TypedDict


class CampaignState(TypedDict, total=False):
    """
    Shared mutable state for the campaign creation workflow.
    All fields are optional (total=False); nodes return only the keys they change.
    """

    # ── User Input ──────────────────────────────────────────────────────────
    user_message: str           # Raw user message for this turn
    mode: str                   # "brainstorm" | "plan" | "execute"
    conversation_id: str        # Unique conversation ID (used for SSE + checkpointing)

    # ── Intent (populated by parse_intent) ──────────────────────────────────
    action: str                 # "brainstorm" | "create_campaign" | "query_customers" | "general_chat"
    audience_description: str   # NL description of the target audience
    message_description: str    # What the message should communicate
    channel: str                # "whatsapp" | "sms" | "email" | "rcs"
    offer_details: str          # Discount or CTA details (e.g. "10% off")

    # ── Brainstorm / Conversation State ─────────────────────────────────────
    brief: Dict[str, Any]       # Campaign brief: {goal, audience, channel, message_idea, offer}
    ai_response: str            # Final text response shown to the user
    suggestions: List[Dict]     # UI suggestion chips: [{label, value, category}]
    ready_to_plan: bool         # True when brief has goal + audience + channel
    brief_updates: Dict[str, Any]  # Updates extracted from this turn only

    # ── Segment (populated by query_customers_db / create_saved_segment) ────
    audience_sql: str           # SQL used to query the audience
    audience_count: int         # Total matching customers
    audience_preview: List[Dict] # Sample rows for the UI preview table
    segment_id: str             # UUID of the saved segment
    segment_name: str           # Human-readable segment name
    filter_criteria: Dict       # JSONB filter criteria for reproducibility

    # ── Message (populated by draft_marketing_message) ──────────────────────
    message_template: str       # Drafted message with {{name}}/{{city}} placeholders
    message_char_count: int     # Character count of the template

    # ── Campaign Execution (populated by execute_saved_campaign) ────────────
    campaign_id: str            # UUID of the created campaign
    campaign_name: str          # Generated campaign name
    total_audience: int         # Final audience count used for the campaign
    communications_created: int # Number of communication records created

    # ── Agent Internal (reset by parse_intent each turn) ────────────────────
    think_pad: str              # LLM chain-of-thought (for debugging / UI display)
    tool_to_call: Optional[str] # Tool chosen by agent_loop (None = respond instead)
    tool_args: Optional[Dict]   # Arguments for the chosen tool
    last_tool_output: str       # Output string from the last tool execution
    tool_calls_count: int       # Safety counter — prevents infinite tool-call loops
    messages: List[Dict]        # Full conversation history: [{role, content}]
    brand_profile_ctx: str      # Brand profile text, fetched once per turn in parse_intent
    current_step: str           # Workflow stage label (debugging / logging)
    error: Optional[str]        # Error message if a step failed