"""
Agent State — TypedDict defining the state that flows through the LangGraph workflow.

The state is checkpointed in Redis at each node, allowing:
  - Resume after interrupts (human-in-the-loop)
  - Crash recovery (state survives server restart)
  - Conversation history persistence
"""

from typing import TypedDict, Optional, Any


class CampaignState(TypedDict, total=False):
    """
    State for the campaign creation workflow.

    This state flows through the LangGraph graph and is checkpointed
    at each node transition. Fields are added progressively as the
    workflow advances through stages.
    """

    # ── User Input ──
    user_message: str           # Original user message
    mode: str                   # "brainstorm", "plan", "execute", or legacy "guided"/"autopilot"
    conversation_id: str        # For persistence

    # ── Intent (parsed from user message) ──
    action: str                 # brainstorm, create_campaign, query_customers, general_chat
    audience_description: str   # NL description of target audience
    message_description: str    # What kind of message to send
    channel: str                # whatsapp, sms, email, rcs
    offer_details: str          # Specific offer/discount

    # ── Brainstorm ──
    brief: dict                 # Accumulated campaign brief: {goal, audience, channel, message_idea, offer}
    ai_response: str            # AI's conversational response text
    suggestions: list           # Structured suggestion chips for the UI
    ready_to_plan: bool         # Whether the brief is complete enough to plan
    brief_updates: dict         # Latest updates to the brief from this exchange

    # ── Segment (built from audience query) ──
    audience_sql: str           # The SQL used to query the audience
    audience_count: int         # Number of matching customers
    audience_preview: list      # Customer preview rows
    segment_id: str             # UUID of saved segment
    segment_name: str           # Generated segment name
    filter_criteria: dict       # JSONB filter for reproducibility

    # ── Message (drafted by LLM) ──
    message_template: str       # The drafted message with {{name}} placeholders
    message_char_count: int     # Character count

    # ── Campaign (final execution) ──
    campaign_id: str            # UUID of created campaign
    campaign_name: str          # Generated campaign name
    total_audience: int         # Final audience count
    communications_created: int # Number of comm records created

    # ── Agent Internal ──
    think_pad: str              # Agent's internal Chain of Thought reasoning
    tool_to_call: str           # Name of the tool the agent wants to execute
    tool_args: dict             # Arguments to pass to the tool
    last_tool_output: str       # Result string returned by the last tool execution
    tool_calls_count: int       # Number of tool executions in this turn to avoid infinite loops
    messages: list              # Conversation messages for context
    current_step: str           # Current workflow step
    error: Optional[str]       # Error message if something failed
