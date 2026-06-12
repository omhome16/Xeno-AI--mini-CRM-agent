"""
Agent Nodes — Functions executed at each step of the LangGraph workflow.
"""

import json
import logging
import re
from typing import Any, Optional

from app.agent.llm import DualLLMClient
from app.agent.prompts import (
    AGENT_LOOP_PROMPT,
)
from app.agent.state import CampaignState
from app.agent import tools as agent_tools

logger = logging.getLogger(__name__)

# Maximum number of tool calls per user turn — prevents infinite loops.
MAX_TOOL_CALLS = 50


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def is_closing_quote(s: str, i: int, n: int) -> bool:
    """
    Look ahead from position i + 1 to see if a double quote acts as a closing quote.
    A closing quote in JSON is followed by :, }, ], or , (with optional whitespace).
    """
    j = i + 1
    while j < n and s[j] in (' ', '\t', '\n', '\r'):
        j += 1
    if j >= n:
        return True # EOF is a valid boundary

    char = s[j]
    if char == ':':
        return True
    if char in ('}', ']'):
        return True
    if char == ',':
        # Verify if comma is followed by another key (string + colon) or block end
        j += 1
        while j < n and s[j] in (' ', '\t', '\n', '\r'):
            j += 1
        if j >= n:
            return True
        if s[j] == '}':
            return True
        if s[j] == '"':
            # Find closing quote of the next key, and verify if it's followed by a colon ':'
            k = j + 1
            escaped = False
            while k < n:
                if s[k] == '\\':
                    escaped = not escaped
                elif s[k] == '"' and not escaped:
                    # Found closing quote, check if followed by colon
                    k += 1
                    while k < n and s[k] in (' ', '\t', '\n', '\r'):
                        k += 1
                    if k < n and s[k] == ':':
                        return True
                    break
                else:
                    escaped = False
                k += 1
            return False
        if s[j] == '{':
            return True
        return False
    return False


def repair_json_string(s: str) -> str:
    """
    Repair common LLM JSON syntax issues:
    - Escapes unescaped double quotes inside string values.
    - Replaces literal newlines/carriage returns inside string values with \\n and \\r.
    """
    result = []
    in_string = False
    escape = False
    i = 0
    n = len(s)

    while i < n:
        char = s[i]

        if char == '\\':
            escape = not escape
            result.append(char)
            i += 1
            continue

        if char == '"':
            if escape:
                result.append(char)
                escape = False
                i += 1
                continue

            if not in_string:
                in_string = True
                result.append(char)
            else:
                if is_closing_quote(s, i, n):
                    in_string = False
                    result.append(char)
                else:
                    # Escape the quote
                    result.append('\\"')
            escape = False
            i += 1
            continue

        escape = False
        if char == '\n':
            if in_string:
                result.append('\\n')
            else:
                result.append(char)
        elif char == '\r':
            if in_string:
                result.append('\\r')
            else:
                result.append(char)
        else:
            result.append(char)
        i += 1

    return "".join(result)


def _parse_json_response(text: str) -> dict:
    """
    Parse a JSON string from an LLM, handling code fences, leading preamble,
    unescaped quotes, and unescaped newlines using a multi-layer strategy.
    """
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    # Layer 1: Direct JSON parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Layer 2: Try repairing and parsing
    try:
        repaired = repair_json_string(text)
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # Layer 3: Extract {...} block
    match = re.search(r"(\{.*\})", text, re.DOTALL)
    if match:
        extracted = match.group(1)
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            pass

        # Layer 4: Try repairing the extracted {...} block
        try:
            repaired_extracted = repair_json_string(extracted)
            return json.loads(repaired_extracted)
        except json.JSONDecodeError:
            pass

    # Fallback to the original direct parse to raise the proper exception
    return json.loads(text)


async def _push_event(conv_id: str, event_type: str, data: dict) -> None:
    """
    Push an SSE event. Silently ignores failures so tool execution is never
    interrupted by a broken SSE connection.
    """
    try:
        from app.sse.manager import push_event
        await push_event(conv_id, event_type, data)
    except Exception as e:
        logger.debug(f"[SSE] push_event failed (non-fatal): {e}")


async def _fetch_brand_profile_ctx() -> str:
    """
    Fetch the brand profile from the database and format it as plain text.
    """
    try:
        from app.database import get_main_pool
        from app.repositories import brand_repo

        pool = get_main_pool()
        profile = await brand_repo.get_brand_profile(pool)
        if not profile:
            return "No brand profile configured. Apply general retail best practices."

        lines = [
            f"Brand Name: {profile.get('brand_name', 'Unknown')}",
            f"Category/Niche: {profile.get('niche', 'Retail')}",
            f"Tone of Voice: {profile.get('brand_tone', 'Professional')}",
        ]

        catalog = profile.get("product_catalog", [])
        if catalog:
            lines.append("Products:")
            for p in catalog:
                lines.append(
                    f"  - {p.get('name')} | \u20b9{p.get('price')} | "
                    f"{p.get('category', '')} | {p.get('description', '')}"
                )

        outlets = profile.get("outlets", [])
        if outlets:
            lines.append("Store Locations:")
            for o in outlets:
                lines.append(f"  - {o.get('name')}, {o.get('city')}: {o.get('address', '')}")

        urls = profile.get("campaign_urls", [])
        if urls:
            lines.append("Campaign URLs / CTAs:")
            for u in urls:
                lines.append(f"  - {u}")

        if profile.get("support_phone"):
            lines.append(f"Support Phone: {profile.get('support_phone')}")

        if profile.get("custom_context"):
            lines.append(f"Brand Notes: {profile.get('custom_context')}")

        return "\n".join(lines)

    except Exception as e:
        logger.warning(f"[_fetch_brand_profile_ctx] Failed: {e}")
        return "No brand profile available."


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 1: SETUP CAMPAIGN STATE
# ═══════════════════════════════════════════════════════════════════════════════

async def setup_campaign_state(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Deterministic state initializer for campaign planning and execution runs.
    """
    logger.info("[setup_campaign_state] Initializing state.")
    brand_profile_ctx = await _fetch_brand_profile_ctx()

    base_reset: dict = {
        "tool_calls_count": 0,
        "last_tool_output": "No tools called yet this turn.",
        "tool_to_call": None,
        "tool_args": None,
        "brand_profile_ctx": brand_profile_ctx,
        "current_step": "state_initialized",
        "action": "create_campaign",
    }

    # Clear execution/plan fields if starting a new plan run to ensure fresh results
    if state.get("mode") == "plan":
        base_reset.update({
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
        })

    return base_reset


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 2: AGENT LOOP
# ═══════════════════════════════════════════════════════════════════════════════

async def agent_loop(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Main reasoning loop. Called repeatedly until the agent decides to respond
    (tool_to_call = None) instead of calling another tool.
    """
    conv_id = state.get("conversation_id", "")
    tool_calls = state.get("tool_calls_count", 0)

    # ── Safety guard: prevent infinite tool loops ────────────────────────────
    if tool_calls >= MAX_TOOL_CALLS:
        logger.warning(f"[agent_loop] Max tool calls ({MAX_TOOL_CALLS}) reached.")
        return {
            "tool_to_call": None,
            "tool_args": None,
            "ai_response": (
                "I've processed the maximum number of steps for this turn. "
                "Please review the current results and continue, or simplify your request."
            ),
            "suggestions": [],
            "current_step": "max_tool_calls_reached",
        }

    # ── Build brief ─────────────────────────────────────────────────────────
    brief = dict(state.get("brief") or {})
    brief_updates = state.get("brief_updates") or {}
    for k, v in brief_updates.items():
        if v:
            brief[k] = v

    # ── Build state context (only non-None values) ───────────────────────────
    state_context = {
        k: v
        for k, v in {
            "audience_sql": state.get("audience_sql"),
            "audience_count": state.get("audience_count"),
            "segment_id": state.get("segment_id"),
            "segment_name": state.get("segment_name"),
            "message_template": state.get("message_template"),
            "message_char_count": state.get("message_char_count"),
            "campaign_id": state.get("campaign_id"),
            "campaign_name": state.get("campaign_name"),
            "total_audience": state.get("total_audience"),
        }.items()
        if v is not None
    }

    user_input = f"User message: {state.get('user_message', '')}"

    # ── Build the system prompt via .format() ────────────────────────────────
    action = state.get("action", "create_campaign")
    system_prompt = AGENT_LOOP_PROMPT.format(
        action=action,
        mode=state.get("mode", "plan"),
        tool_calls_count=tool_calls,
        brief=json.dumps(brief, indent=2, ensure_ascii=False) if brief else "{}",
        state_context=json.dumps(state_context, indent=2) if state_context else "{}",
        brand_profile=state.get("brand_profile_ctx") or "No brand profile available.",
        last_tool_output=state.get("last_tool_output") or "No tools called yet.",
    )

    # ── SSE: inform the user we are thinking ────────────────────────────────
    await _push_event(conv_id, "step_start", {
        "step": "Reasoning",
        "message": f"Analyzing request (step {tool_calls + 1})...",
    })

    # ── LLM Call ─────────────────────────────────────────────────────────────
    try:
        raw = await llm_client.reason(system_prompt, user_input)
        parsed = _parse_json_response(raw)
    except Exception as e:
        logger.error(f"[agent_loop] LLM reasoning failed: {e}. Raw response:\n{raw}", exc_info=True)
        existing_think = state.get("think_pad") or ""
        error_think = f"Reasoning engine error: {e}"
        think_pad = f"{existing_think}\n\n{error_think}" if existing_think else error_think

        return {
            "think_pad": think_pad,
            "tool_to_call": None,
            "tool_args": None,
            "ai_response": "I encountered a temporary error. Please try again.",
            "suggestions": [],
            "brief_updates": {},
            "ready_to_plan": False,
            "current_step": "agent_loop_error",
        }

    # ── Extract & validate parsed values ────────────────────────────────────
    think_pad = parsed.get("think_pad", "")
    tool_to_call = parsed.get("tool_to_call")
    tool_args = parsed.get("tool_args") or {}
    response = parsed.get("response") or ""
    suggestions = parsed.get("suggestions") or []
    new_brief_updates = parsed.get("brief_updates") or {}
    ready_to_plan = bool(parsed.get("ready_to_plan", False))

    if isinstance(tool_to_call, str) and tool_to_call.lower() in ("null", "none", ""):
        tool_to_call = None

    for k, v in new_brief_updates.items():
        if v:
            brief[k] = v

    logger.info(
        f"[agent_loop] iter={tool_calls + 1} tool_to_call={tool_to_call!r} "
        f"ready_to_plan={ready_to_plan} think={think_pad[:80]!r}"
    )

    existing_think = state.get("think_pad") or ""
    if existing_think and think_pad:
        think_pad = f"{existing_think}\n\n{think_pad}"
    elif not think_pad:
        think_pad = existing_think

    return {
        "think_pad": think_pad,
        "tool_to_call": tool_to_call,
        "tool_args": tool_args,
        "ai_response": response,
        "suggestions": suggestions,
        "brief": brief,
        "brief_updates": new_brief_updates,
        "ready_to_plan": ready_to_plan,
        "current_step": f"agent_loop_iter_{tool_calls + 1}",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NODE 3: CALL TOOL
# ═══════════════════════════════════════════════════════════════════════════════

async def call_tool(state: CampaignState, llm_client: DualLLMClient) -> dict:
    """
    Execute the tool chosen by agent_loop (state.tool_to_call).
    """
    conv_id = state.get("conversation_id", "")
    tool_name = state.get("tool_to_call")
    tool_args = state.get("tool_args") or {}
    tool_calls = state.get("tool_calls_count", 0)

    logger.info(f"[call_tool] Executing tool={tool_name!r} args={tool_args}")

    last_tool_output = ""
    updates: dict = {}

    if tool_name == "query_customers_db":
        query_desc = (
            tool_args.get("query_description")
            or state.get("audience_description")
            or "all customers"
        )
        await _push_event(conv_id, "step_start", {
            "step": "Database Query",
            "message": f"Querying customers: \"{query_desc[:60]}\"...",
        })
        try:
            res = await agent_tools.query_customers(llm_client, query_desc)
            if res.get("error"):
                last_tool_output = f"ERROR: {res['error']}"
            else:
                last_tool_output = (
                    f"Query successful. Total matching customers: {res['count']}. "
                    f"SQL used: {res['sql']}. "
                    f"Preview ({len(res['results'])} rows): {json.dumps(res['results'][:5])}"
                )
                updates = {
                    "audience_sql": res["sql"],
                    "audience_count": res["count"],
                    "audience_preview": res["results"],
                }
        except Exception as e:
            logger.error(f"[call_tool] query_customers_db crashed: {e}", exc_info=True)
            last_tool_output = f"ERROR: Tool crashed — {e}"

    elif tool_name == "create_saved_segment":
        aud_desc = (
            tool_args.get("audience_description")
            or state.get("audience_description")
            or "all customers"
        )
        count = (
            tool_args.get("customer_count")
            or state.get("audience_count")
            or 0
        )
        await _push_event(conv_id, "step_start", {
            "step": "Saving Segment",
            "message": f"Saving segment for {count} customers...",
        })
        try:
            res = await agent_tools.create_segment(llm_client, aud_desc, count)
            if res.get("error"):
                last_tool_output = f"ERROR: {res['error']}"
            else:
                last_tool_output = (
                    f"Segment saved. segment_id={res['segment_id']}, "
                    f"name=\"{res['name']}\", customer_count={res['customer_count']}."
                )
                updates = {
                    "segment_id": res["segment_id"],
                    "segment_name": res["name"],
                    "filter_criteria": res["filter_criteria"],
                }
        except Exception as e:
            logger.error(f"[call_tool] create_saved_segment crashed: {e}", exc_info=True)
            last_tool_output = f"ERROR: Tool crashed — {e}"

    elif tool_name == "draft_marketing_message":
        if state.get("message_template") and state.get("mode") == "execute":
            last_tool_output = (
                "Message drafting skipped — existing message_template found in state."
            )
        else:
            chan = (
                tool_args.get("channel")
                or state.get("channel")
                or "whatsapp"
            )
            aud_desc = (
                tool_args.get("audience_description")
                or state.get("audience_description")
                or ""
            )
            msg_desc = (
                tool_args.get("message_description")
                or state.get("message_description")
                or ""
            )
            offer = (
                tool_args.get("offer_details")
                or state.get("offer_details")
                or ""
            )
            await _push_event(conv_id, "step_start", {
                "step": "Drafting Message",
                "message": f"Writing {chan.upper()} message copy...",
            })
            try:
                res = await agent_tools.generate_message(
                    llm_client,
                    chan,
                    aud_desc,
                    msg_desc,
                    offer,
                    brand_profile_ctx=state.get("brand_profile_ctx", ""),
                )
                last_tool_output = (
                    f"Message drafted ({res['char_count']} chars) for {chan}. "
                    f"Template preview: {res['message_template'][:120]}..."
                )
                updates = {
                    "message_template": res["message_template"],
                    "message_char_count": res["char_count"],
                }
            except Exception as e:
                logger.error(f"[call_tool] draft_marketing_message crashed: {e}", exc_info=True)
                last_tool_output = f"ERROR: Tool crashed — {e}"

    elif tool_name == "execute_saved_campaign":
        seg_id = tool_args.get("segment_id") or state.get("segment_id")
        chan = tool_args.get("channel") or state.get("channel") or "whatsapp"
        template = tool_args.get("message_template") or state.get("message_template")
        aud_sql = tool_args.get("audience_sql") or state.get("audience_sql")
        seg_name = state.get("segment_name") or "Campaign"
        campaign_name = f"{seg_name} — {chan.upper()}"

        missing = [k for k, v in {
            "segment_id": seg_id,
            "message_template": template,
            "audience_sql": aud_sql,
        }.items() if not v]

        if missing:
            last_tool_output = (
                f"ERROR: Cannot execute campaign — missing: {', '.join(missing)}. "
                "Run the earlier steps first."
            )
        else:
            await _push_event(conv_id, "step_start", {
                "step": "Launching Campaign",
                "message": "Creating campaign and communications...",
            })
            try:
                res = await agent_tools.execute_campaign(
                    llm_client, seg_id, chan, template, campaign_name, aud_sql
                )
                if res.get("error"):
                    last_tool_output = f"ERROR: {res['error']}"
                else:
                    last_tool_output = (
                        f"Campaign launched. campaign_id={res['campaign_id']}, "
                        f"total_audience={res['total_audience']}, "
                        f"communications_created={res['communications_created']}."
                    )
                    updates = {
                        "campaign_id": res["campaign_id"],
                        "campaign_name": campaign_name,
                        "total_audience": res["total_audience"],
                        "communications_created": res["communications_created"],
                    }
            except Exception as e:
                logger.error(f"[call_tool] execute_saved_campaign crashed: {e}", exc_info=True)
                last_tool_output = f"ERROR: Tool crashed — {e}"

    else:
        last_tool_output = f"ERROR: Unknown tool name '{tool_name}'. No action taken."
        logger.warning(f"[call_tool] Unknown tool: {tool_name!r}")

    logger.info(f"[call_tool] Result: {last_tool_output[:120]}")

    return {
        **updates,
        "tool_to_call": None,
        "tool_args": None,
        "last_tool_output": last_tool_output,
        "tool_calls_count": tool_calls + 1,
        "current_step": f"tool_executed_{tool_name or 'unknown'}",
    }