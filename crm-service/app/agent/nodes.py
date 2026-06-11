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
    AGENT_LOOP_PROMPT,
    GENERAL_RESPONSE_PROMPT,
)
from app.agent import tools as agent_tools

logger = logging.getLogger(__name__)


def _parse_json_response(text: str) -> dict:
    """Parse a JSON response from an LLM, handling code fences and preambles."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        import re
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as inner_e:
                raise inner_e
        logger.warning(f"Failed to parse JSON: {text[:200]}")
        raise e


async def _execute_brainstorm_query(sql: str) -> str:
    """Execute a read-only query safely for brainstorming context."""
    from app.services.sql_guard import SQLGuard, SQLGuardError
    from app.database import get_readonly_pool
    
    sql = sql.strip()
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    sql = sql.rstrip(";")
    
    guard = SQLGuard()
    try:
        safe_sql = guard.validate_and_prepare(sql)
    except SQLGuardError as e:
        logger.warning(f"Brainstorm query rejected by SQLGuard: {e}")
        return f"Query rejected: {e}"
        
    readonly_pool = get_readonly_pool()
    try:
        async with readonly_pool.acquire() as conn:
            await conn.execute("SET statement_timeout = '3000'")
            rows = await conn.fetch(safe_sql)
            results = []
            for r in rows[:15]:  # Limit to 15 items for context
                record = {}
                for k, v in dict(r).items():
                    if hasattr(v, 'isoformat'):
                        record[k] = v.isoformat()
                    elif isinstance(v, (int, float, str, bool)) or v is None:
                        record[k] = v
                    else:
                        record[k] = str(v)
                results.append(record)
            return json.dumps(results, indent=2)
    except Exception as e:
        logger.warning(f"Brainstorm query execution failed: {e}")
        return f"Execution error: {e}"


async def parse_intent(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Parse the user's natural language message into structured intent.

    Input: state.user_message, state.messages (conversation history)
    Output: action, audience_description, message_description, channel, offer_details, brief_updates, think_pad
    """
    # Bypass intent parsing if we are in plan or execute mode to preserve explicit specifications
    if state.get("mode") in ("plan", "execute"):
        logger.info(f"Bypassing intent parsing for mode: {state['mode']}")
        
        # When starting a new plan, clear previous campaign details
        clear_fields = {}
        if state.get("mode") == "plan":
            clear_fields = {
                "audience_sql": None,
                "audience_count": None,
                "audience_preview": None,
                "segment_id": None,
                "segment_name": None,
                "filter_criteria": None,
                "message_template": None,
                "message_char_count": None,
                "campaign_id": None,
                "campaign_name": None,
                "total_audience": None,
                "communications_created": None,
            }
            
        return {
            "think_pad": f"Bypassing intent parsing in {state['mode']} mode.",
            "action": state.get("action", "create_campaign"),
            "audience_description": state.get("audience_description", ""),
            "message_description": state.get("message_description", ""),
            "channel": state.get("channel", "") or "",
            "offer_details": state.get("offer_details", ""),
            "brief_updates": state.get("brief_updates", {}),
            "tool_calls_count": 0,
            "last_tool_output": "No tools run yet in this turn.",
            "tool_to_call": None,
            "tool_args": None,
            "current_step": "intent_parsed",
            **clear_fields,
        }

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

    try:
        result = await llm_client.reason(
            system_prompt=INTENT_PARSING_PROMPT,
            user_input=user_input,
        )
        intent = _parse_json_response(result)
    except Exception as e:
        logger.error(f"Intent parsing failed: {e}")
        intent = {
            "think_pad": f"Failed to connect to AI reasoning service: {e}. Defaulting to brainstorm mode.",
            "action": "brainstorm",
            "audience_description": "",
            "message_description": "",
            "channel": None,
            "offer_details": None,
            "brief_updates": {},
        }

    return {
        "think_pad": intent.get("think_pad", "No reasoning recorded by intent parser."),
        "action": intent.get("action", "general_chat"),
        "audience_description": intent.get("audience_description", ""),
        "message_description": intent.get("message_description", ""),
        "channel": intent.get("channel", "") or "",
        "offer_details": intent.get("offer_details", ""),
        "brief_updates": intent.get("brief_updates", {}),
        "tool_calls_count": 0,
        "last_tool_output": "No tools run yet in this turn.",
        "tool_to_call": None,
        "tool_args": None,
        "current_step": "intent_parsed",
        # Clear previous campaign execution details so they don't pollute the new turn
        "audience_sql": None,
        "audience_count": None,
        "audience_preview": None,
        "segment_id": None,
        "segment_name": None,
        "filter_criteria": None,
        "message_template": None,
        "message_char_count": None,
        "campaign_id": None,
        "campaign_name": None,
        "total_audience": None,
        "communications_created": None,
    }


async def agent_loop(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Dynamic reasoning node. Decides whether to call a tool or compile a response.
    """
    from app.sse.manager import push_event
    conv_id = state.get("conversation_id", "")

    # Initialize counts and scratchpads
    tool_calls = state.get("tool_calls_count", 0)
    last_tool_output = state.get("last_tool_output", "No tools run yet in this turn.")
    brief = dict(state.get("brief", {}))

    # Note: Removed the safety counter limit of 5 tool calls as requested.

    # Merge brief updates from state
    brief_updates = state.get("brief_updates", {}) or {}
    for k, v in brief_updates.items():
        if v:
            brief[k] = v

    # Build history context
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
            "Conversation context:\n"
            + "\n".join(context_parts)
            + f"\n\nLatest user input: {state['user_message']}"
        )

    # Construct loop prompt
    action = state.get("action", "general_chat")
    if action == "general_chat":
        system_prompt = GENERAL_RESPONSE_PROMPT
    else:
        brief_text = json.dumps(brief, indent=2) if brief else "Empty brief"
        brand_profile_ctx = await _get_brand_profile_context()

        system_prompt = AGENT_LOOP_PROMPT.replace("{brief}", brief_text)
        system_prompt = system_prompt.replace("{brand_profile}", brand_profile_ctx)
        system_prompt = system_prompt.replace("{last_tool_output}", last_tool_output)

        # Inject operational mode instructions
        mode = state.get("mode", "brainstorm")
        if mode == "plan":
            system_prompt += (
                "\n\n[CRITICAL OPERATIONAL INSTRUCTION]\n"
                "You are in 'plan' mode. You must construct a complete campaign plan. Proceed as follows:\n"
                "1. If you don't have the audience count yet (i.e. state.audience_count is missing or 0), call the `query_customers_db` tool using the target audience description.\n"
                "2. If you have the audience count, but have not created/saved the segment (i.e. state.segment_id is missing or null), call the `create_saved_segment` tool.\n"
                "3. If you have the segment_id, but have not drafted the message template (i.e. state.message_template is missing or null), call the `draft_marketing_message` tool.\n"
                "4. Once you have segment_id AND message_template, do NOT call any more tools. Set `tool_to_call` to null and set `ready_to_plan` to true."
            )
        elif mode == "execute":
            system_prompt += (
                "\n\n[CRITICAL OPERATIONAL INSTRUCTION]\n"
                "You are in 'execute' mode. You must launch the campaign. Proceed as follows:\n"
                "1. Check if the campaign has been launched (i.e. state.campaign_id is set). If not, call the `execute_saved_campaign` tool with segment_id, channel, message_template, and audience_sql from the state.\n"
                "2. Once the execution is complete (i.e. campaign_id is returned), set `tool_to_call` to null, summarize the success, and output the results."
            )

        # Append current state values for context
        state_context = {
            "mode": state.get("mode"),
            "audience_sql": state.get("audience_sql"),
            "audience_count": state.get("audience_count"),
            "segment_id": state.get("segment_id"),
            "segment_name": state.get("segment_name"),
            "message_template": state.get("message_template"),
            "campaign_id": state.get("campaign_id"),
        }
        state_ctx_text = json.dumps({k: v for k, v in state_context.items() if v is not None}, indent=2)
        system_prompt += f"\n\nCURRENT GRAPH STATE VARIABLES:\n{state_ctx_text}"

    await push_event(conv_id, "step_start", {
        "step": "Analyzing State",
        "message": "AI is reasoning and planning next steps...",
    })

    try:
        result = await llm_client.reason(
            system_prompt=system_prompt,
            user_input=user_input,
        )
        parsed = _parse_json_response(result)
    except Exception as e:
        logger.error(f"Agent reasoning failed: {e}", exc_info=True)
        parsed = {
            "think_pad": f"Reasoning engine failed with error: {e}. Falling back to default response.",
            "tool_to_call": None,
            "tool_args": None,
            "response": "I encountered a minor issue connecting to my reasoning engine. Let's continue setting up your campaign. What channel would you like to use?",
            "suggestions": [
                {"label": "WhatsApp", "value": "WhatsApp", "category": "channel"},
                {"label": "Email", "value": "Email", "category": "channel"},
                {"label": "SMS", "value": "SMS", "category": "channel"}
            ],
            "brief_updates": {},
            "ready_to_plan": False
        }

    # Extract values
    think_pad = parsed.get("think_pad", "No reasoning recorded.")
    tool_to_call = parsed.get("tool_to_call")
    tool_args = parsed.get("tool_args") or {}
    response = parsed.get("response", "Let's brainstorm campaign details!")
    suggestions = parsed.get("suggestions", [])
    new_brief_updates = parsed.get("brief_updates", {}) or {}
    ready_to_plan = parsed.get("ready_to_plan", False)

    # If tool_to_call is returned but is null/none in string format
    if isinstance(tool_to_call, str) and tool_to_call.lower() in ("null", "none"):
        tool_to_call = None

    # Update brief with new updates from this loop iteration
    for k, v in new_brief_updates.items():
        if v:
            brief[k] = v

    logger.info(f"[agent_loop] Think Pad: {think_pad}")
    if tool_to_call:
        logger.info(f"[agent_loop] Decided to call tool: {tool_to_call} with args: {tool_args}")

    return {
        "think_pad": think_pad,
        "tool_to_call": tool_to_call,
        "tool_args": tool_args,
        "ai_response": response,
        "suggestions": suggestions,
        "brief": brief,
        "brief_updates": new_brief_updates,
        "ready_to_plan": ready_to_plan,
        "current_step": "agent_loop_completed"
    }


async def call_tool(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Executes the tool specified by state.tool_to_call.
    """
    from app.sse.manager import push_event
    conv_id = state.get("conversation_id", "")
    tool_name = state.get("tool_to_call")
    tool_args = state.get("tool_args") or {}
    tool_calls = state.get("tool_calls_count", 0)

    logger.info(f"[call_tool] Executing tool: {tool_name} with arguments: {tool_args}")

    last_tool_output = ""
    updates = {}

    if tool_name == "query_customers_db":
        query_desc = tool_args.get("query_description", state.get("audience_description", "all customers"))
        await push_event(conv_id, "step_start", {
            "step": "Database Query",
            "message": f"Querying customer database: \"{query_desc[:60]}\"...",
        })
        try:
            res = await agent_tools.query_customers(llm_client, query_desc)
            if res.get("error"):
                last_tool_output = f"Database query failed: {res['error']}"
            else:
                last_tool_output = f"Successfully queried database. Found {res['count']} customers. SQL: {res['sql']}."
                updates = {
                    "audience_sql": res["sql"],
                    "audience_count": res["count"],
                    "audience_preview": res["results"],
                }
        except Exception as e:
            logger.error(f"Tool execution query_customers_db crashed: {e}")
            last_tool_output = f"Crashed running query_customers_db: {e}"

    elif tool_name == "create_saved_segment":
        aud_desc = tool_args.get("audience_description", state.get("audience_description", "all customers"))
        count = tool_args.get("customer_count", state.get("audience_count", 0))
        await push_event(conv_id, "step_start", {
            "step": "Saving Segment",
            "message": f"Saving segment for \"{aud_desc[:60]}\" with {count} customers...",
        })
        try:
            res = await agent_tools.create_segment(llm_client, aud_desc, count)
            last_tool_output = f"Successfully saved segment with ID: {res['segment_id']}, Name: {res['name']}."
            updates = {
                "segment_id": res["segment_id"],
                "segment_name": res["name"],
                "filter_criteria": res["filter_criteria"],
            }
        except Exception as e:
            logger.error(f"Tool execution create_saved_segment crashed: {e}")
            last_tool_output = f"Crashed running create_saved_segment: {e}"

    elif tool_name == "draft_marketing_message":
        chan = tool_args.get("channel", state.get("channel", "whatsapp"))
        aud_desc = tool_args.get("audience_description", state.get("audience_description", ""))
        msg_desc = tool_args.get("message_description", state.get("message_description", ""))
        offer = tool_args.get("offer_details", state.get("offer_details", ""))
        
        await push_event(conv_id, "step_start", {
            "step": f"Drafting {chan.upper()} Message",
            "message": f"Generating message draft for {chan}...",
        })
        try:
            if state.get("message_template") and state.get("mode") == "execute":
                last_tool_output = "Message template drafting skipped because custom template is already defined in state."
            else:
                res = await agent_tools.generate_message(llm_client, chan, aud_desc, msg_desc, offer)
                last_tool_output = f"Successfully generated message template ({res['char_count']} characters)."
                updates = {
                    "message_template": res["message_template"],
                    "message_char_count": res["char_count"],
                }
        except Exception as e:
            logger.error(f"Tool execution draft_marketing_message crashed: {e}")
            last_tool_output = f"Crashed running draft_marketing_message: {e}"

    elif tool_name == "execute_saved_campaign":
        seg_id = tool_args.get("segment_id", state.get("segment_id"))
        chan = tool_args.get("channel", state.get("channel", "whatsapp"))
        template = tool_args.get("message_template", state.get("message_template"))
        aud_sql = tool_args.get("audience_sql", state.get("audience_sql"))
        
        if not seg_id or not template or not aud_sql:
            last_tool_output = f"Failed to execute campaign: missing parameters (segment_id: {seg_id is not None}, message_template: {template is not None}, audience_sql: {aud_sql is not None})."
        else:
            await push_event(conv_id, "step_start", {
                "step": "Executing Campaign",
                "message": f"Creating campaign and launching communications...",
            })
            try:
                campaign_name = f"{state.get('segment_name', 'Campaign')} — {chan.upper()}"
                res = await agent_tools.execute_campaign(llm_client, seg_id, chan, template, campaign_name, aud_sql)
                
                if res.get("error"):
                    last_tool_output = f"Campaign execution failed: {res['error']}"
                else:
                    last_tool_output = f"Successfully executed campaign. Campaign ID: {res['campaign_id']}, Total Audience: {res['total_audience']}."
                    updates = {
                        "campaign_id": res["campaign_id"],
                        "campaign_name": campaign_name,
                        "total_audience": res["total_audience"],
                        "communications_created": res["communications_created"],
                    }
                    from app.services.redis_queue import push_to_queue
                    push_to_queue("crm_dispatch_queue", {
                        "campaign_id": res["campaign_id"],
                        "conversation_id": conv_id
                    })
            except Exception as e:
                logger.error(f"Tool execution execute_saved_campaign crashed: {e}")
                last_tool_output = f"Crashed running execute_saved_campaign: {e}"

    else:
        last_tool_output = f"Unknown tool name: {tool_name}"
        logger.warning(f"[call_tool] Received unknown tool name: {tool_name}")

    logger.info(f"[call_tool] Execution finished. Output: {last_tool_output}")

    return {
        **updates,
        "tool_to_call": None,
        "tool_args": None,
        "last_tool_output": last_tool_output,
        "tool_calls_count": tool_calls + 1,
        "current_step": f"tool_executed_{tool_name}" if tool_name else "tool_execution_failed",
    }


async def respond_brainstorm(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Compile final brainstorm state.
    """
    logger.info("[respond_brainstorm] Compiling final brainstorm state.")
    return {
        "ai_response": state.get("ai_response"),
        "suggestions": state.get("suggestions"),
        "brief": state.get("brief"),
        "brief_updates": state.get("brief_updates"),
        "ready_to_plan": state.get("ready_to_plan"),
        "think_pad": state.get("think_pad"),
        "current_step": "brainstorm_responded"
    }


async def respond_general(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Compile general chat response.
    """
    logger.info("[respond_general] Compiling general chat response.")
    return {
        "ai_response": state.get("ai_response"),
        "think_pad": state.get("think_pad"),
        "current_step": "general_responded"
    }


async def build_segment(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Compile final segment build results.
    """
    logger.info("[build_segment] Compiling final segment build results.")
    return {
        "audience_sql": state.get("audience_sql"),
        "audience_count": state.get("audience_count"),
        "audience_preview": state.get("audience_preview"),
        "segment_id": state.get("segment_id"),
        "segment_name": state.get("segment_name"),
        "filter_criteria": state.get("filter_criteria"),
        "current_step": "segment_built"
    }


async def draft_message(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Compile final message template draft.
    """
    logger.info("[draft_message] Compiling final message template draft.")
    return {
        "message_template": state.get("message_template"),
        "message_char_count": state.get("message_char_count"),
        "current_step": "message_drafted"
    }


async def execute_campaign(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Compile final campaign execution results.
    """
    logger.info("[execute_campaign] Compiling final campaign execution results.")
    return {
        "campaign_id": state.get("campaign_id"),
        "campaign_name": state.get("campaign_name"),
        "total_audience": state.get("total_audience"),
        "communications_created": state.get("communications_created"),
        "current_step": "campaign_executing"
    }


async def _get_brand_profile_context() -> str:
    """Helper to fetch brand profile and format it for LLM context."""
    try:
        from app.database import get_main_pool
        from app.repositories import brand_repo
        pool = get_main_pool()
        profile = await brand_repo.get_brand_profile(pool)
        if not profile:
            return "No brand profile configured. General retail brand context applies."
        
        # Format profile as text
        context_lines = [
            f"Brand Name: {profile.get('brand_name')}",
            f"Niche/Category: {profile.get('niche')}",
            f"Tone of voice: {profile.get('brand_tone', 'Professional')}"
        ]
        
        catalog = profile.get("product_catalog", [])
        if catalog:
            context_lines.append("Product Catalog:")
            for p in catalog:
                context_lines.append(f"  - {p.get('name')} (Price: \u20b9{p.get('price')}, Category: {p.get('category', 'None')}) - {p.get('description', '')}")
                
        outlets = profile.get("outlets", [])
        if outlets:
            context_lines.append("Store Locations:")
            for o in outlets:
                context_lines.append(f"  - {o.get('name')} in {o.get('city')} ({o.get('address', '')})")
                
        urls = profile.get("campaign_urls", [])
        if urls:
            context_lines.append("Promotional URLs / CTAs to include in copy:")
            for u in urls:
                context_lines.append(f"  - {u}")
                
        if profile.get("support_phone"):
            context_lines.append(f"Customer Support Phone: {profile.get('support_phone')}")
            
        if profile.get("custom_context"):
            context_lines.append(f"Additional Context/Guidelines: {profile.get('custom_context')}")
            
        return "\n".join(context_lines)
    except Exception as e:
        logger.warning(f"Error fetching brand profile: {e}")
        return "No brand profile configured. General retail brand context applies."
