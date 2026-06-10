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
    mode: str                   # "guided" or "autopilot"
    conversation_id: str        # For persistence

    # ── Intent (parsed from user message) ──
    action: str                 # create_campaign, query_customers, analytics, general_chat
    audience_description: str   # NL description of target audience
    message_description: str    # What kind of message to send
    channel: str                # whatsapp, sms, email, rcs
    offer_details: str          # Specific offer/discount

    # ── Segment (built from audience query) ──
    audience_sql: str           # The SQL used to query the audience
    audience_count: int         # Number of matching customers
    audience_preview: list      # First 10 customers for preview
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
    messages: list              # Conversation messages for context
    current_step: str           # Current workflow step
    error: Optional[str]       # Error message if something failed
