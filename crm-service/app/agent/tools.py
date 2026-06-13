"""
Agent Tools — Async functions the LangGraph agent can invoke via the call_tool node.

Each tool is a standalone async function that interacts with the database or LLM.
Tools are called by name from call_tool in nodes.py based on agent_loop's decision.

Available Tools:
  query_customers     — NL → SQL → execute → return results + count
  create_segment      — NL → JSONB filter → save segment → return segment_id
  generate_message    — Draft a channel-appropriate marketing message
  execute_campaign    — Create campaign + communication records + queue dispatch
"""

import json
import logging
import re
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from langsmith import traceable

from app.agent.prompts import (
    CAMPAIGN_NAMING_PROMPT,
    FILTER_GENERATION_PROMPT,
    MESSAGE_GENERATION_PROMPT,
    SQL_GENERATION_PROMPT,
)
from app.database import get_main_pool, get_readonly_pool
from app.repositories import campaign_repo
from app.services.sql_guard import SQLGuard, SQLGuardError

logger = logging.getLogger(__name__)

_sql_guard = SQLGuard()


# ═══════════════════════════════════════════════════════════════════════════════
# 1. QUERY CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════════

@traceable(run_type="tool")
async def query_customers(llm_client, audience_description: str) -> dict:
    """
    Convert natural language to SQL, validate, execute, and return results.

    Flow:
      1. LLM generates a PostgreSQL SELECT query.
      2. SQLGuard validates it (read-only, LIMIT enforced).
      3. Execute against the read-only connection pool.
      4. Count total rows (separate COUNT(*) query without LIMIT).
      5. Return sql, results (preview rows), and count (total).

    Returns:
        Dict with keys: sql, results, count, error (on failure).
    """
    # Step 1: Generate SQL
    try:
        raw_sql = await llm_client.generate(
            system_prompt=SQL_GENERATION_PROMPT,
            user_input=audience_description,
        )
    except Exception as e:
        logger.error(f"[query_customers] SQL generation failed: {e}")
        return {
            "error": f"Could not translate your description to SQL: {str(e)[:200]}",
            "sql": "",
            "results": [],
            "count": 0,
        }

    # Clean LLM output (strip code fences if present)
    sql = raw_sql.strip()
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    sql = sql.rstrip(";")

    # Step 2: Validate with SQLGuard
    try:
        safe_sql = _sql_guard.validate_and_prepare(sql)
    except SQLGuardError as e:
        logger.warning(f"[query_customers] SQL rejected by guard: {e} | SQL: {sql[:200]}")
        return {
            "error": f"The generated query was rejected for safety: {e}",
            "sql": sql,
            "results": [],
            "count": 0,
        }

    # Step 3 + 4: Execute and count
    readonly_pool = get_readonly_pool()
    try:
        async with readonly_pool.acquire() as conn:
            await conn.execute("SET statement_timeout = '5000'")

            # Fetch preview rows (LIMIT already added by SQLGuard)
            rows = await conn.fetch(safe_sql)

            # Count total rows without LIMIT/ORDER BY
            count_sql = re.sub(r"\s+LIMIT\s+\d+", "", safe_sql, flags=re.IGNORECASE)
            count_sql = re.sub(
                r"\s+ORDER\s+BY\s+[\w\s.,\"'`]+?(?=(?:LIMIT|$))", "",
                count_sql, flags=re.IGNORECASE,
            )
            count_sql = f"SELECT COUNT(*) AS total FROM ({count_sql.strip()}) _sub"

            try:
                count_row = await conn.fetchrow(count_sql)
                total_count = int(count_row["total"]) if count_row else len(rows)
            except Exception as count_err:
                logger.warning(f"[query_customers] Count query failed: {count_err}")
                total_count = len(rows)

    except Exception as e:
        logger.error(f"[query_customers] Execution failed: {e}")
        return {
            "error": f"Query execution failed: {str(e)[:200]}",
            "sql": safe_sql,
            "results": [],
            "count": 0,
        }

    # Step 5: Serialize rows (handle UUID, Decimal, datetime)
    results = [_serialize_row(dict(row)) for row in rows]

    logger.info(f"[query_customers] Found {total_count} total customers. Returning {len(results)} preview rows.")
    return {
        "sql": safe_sql,
        "results": results,
        "count": total_count,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 2. CREATE SEGMENT
# ═══════════════════════════════════════════════════════════════════════════════

@traceable(run_type="tool")
async def create_segment(
    llm_client,
    audience_description: str,
    customer_count: int,
) -> dict:
    """
    Generate a JSONB filter and save the segment to the database.

    Flow:
      1. LLM generates a JSONB filter from the NL audience description.
      2. LLM generates a short, descriptive segment name.
      3. Save to the segments table via campaign_repo.
      4. Return segment_id, name, filter_criteria.

    Returns:
        Dict with keys: segment_id, name, filter_criteria, customer_count, error (on failure).
    """
    pool = get_main_pool()

    # Step 1: Generate JSONB filter
    try:
        filter_raw = await llm_client.reason(
            system_prompt=FILTER_GENERATION_PROMPT,
            user_input=audience_description,
        )
        from app.agent.nodes import _parse_json_response
        filter_criteria = _parse_json_response(filter_raw)
    except Exception as e:
        logger.warning(f"[create_segment] Filter generation failed: {e}. Using fallback.")
        filter_criteria = {"filters": []}  # Safe fallback: matches all customers

    # Step 2: Generate segment name
    try:
        name_raw = await llm_client.generate(
            system_prompt=CAMPAIGN_NAMING_PROMPT,
            user_input=f"Audience: {audience_description}",
        )
        name = name_raw.strip().strip('"').strip("'")[:100]
    except Exception as e:
        logger.warning(f"[create_segment] Name generation failed: {e}. Using fallback.")
        name = f"Segment: {audience_description[:60]}"

    # Step 3: Save segment
    try:
        segment_id = await campaign_repo.create_segment(
            pool=pool,
            name=name,
            description=audience_description,
            filter_criteria=filter_criteria,
            customer_count=customer_count,
        )
    except Exception as e:
        logger.error(f"[create_segment] DB save failed: {e}")
        return {
            "error": f"Failed to save segment to database: {str(e)[:200]}",
            "segment_id": None,
            "name": name,
            "filter_criteria": filter_criteria,
            "customer_count": customer_count,
        }

    logger.info(f"[create_segment] Saved segment '{name}' with ID {segment_id}.")
    return {
        "segment_id": str(segment_id),
        "name": name,
        "filter_criteria": filter_criteria,
        "customer_count": customer_count,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 3. GENERATE MESSAGE
# ═══════════════════════════════════════════════════════════════════════════════

@traceable(run_type="tool")
async def generate_message(
    llm_client,
    channel: str,
    audience_description: str,
    message_description: str,
    offer_details: str = "",
    brand_profile_ctx: str = "",
) -> dict:
    """
    Draft a personalized, channel-appropriate marketing message.

    If brand_profile_ctx is provided (pre-fetched by parse_intent and cached in state),
    it is used directly — avoiding a redundant DB query.
    If empty, it falls back to fetching the brand profile from the database.

    Returns:
        Dict with keys: message_template, channel, char_count.
    """
    # Use cached brand profile if available; otherwise fetch from DB
    if not brand_profile_ctx:
        brand_profile_ctx = await _fetch_brand_profile_ctx()

    context = (
        f"Channel: {channel}\n"
        f"Audience: {audience_description}\n"
        f"Message goal: {message_description}\n"
        f"Offer details: {offer_details or 'None specified'}"
    )

    sys_prompt = MESSAGE_GENERATION_PROMPT.format(
        context=context,
        brand_profile=brand_profile_ctx,
    )

    try:
        message = await llm_client.generate(
            system_prompt=sys_prompt,
            user_input=context,
        )
        message = message.strip()
    except Exception as e:
        logger.error(f"[generate_message] LLM call failed: {e}")
        # Safe fallback — avoids crashing the whole campaign flow
        message = (
            f"Hello {{{{name}}}}, we have a special offer waiting for you in {{{{city}}}}! "
            f"{offer_details or 'Check out our latest deals.'} "
            f"Visit us today."
        )

    logger.info(f"[generate_message] Drafted {channel} message ({len(message)} chars).")
    return {
        "message_template": message,
        "channel": channel,
        "char_count": len(message),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 4. EXECUTE CAMPAIGN
# ═══════════════════════════════════════════════════════════════════════════════

@traceable(run_type="tool")
async def execute_campaign(
    llm_client,
    segment_id: str,
    channel: str,
    message_template: str,
    campaign_name: str,
    audience_sql: str,
    conversation_id: Optional[str] = None,
) -> dict:
    """
    Execute the campaign: re-query the audience, create the campaign record,
    create communication records, and queue for dispatch.

    Flow:
      1. Validate all required parameters.
      2. Re-run audience_sql against the read-only pool to get current customers.
      3. Create a campaign record in the campaigns table.
      4. Bulk-create communication records for each customer.
      5. Queue the campaign_id for the dispatch worker.

    Returns:
        Dict with keys: campaign_id, total_audience, communications_created, error (on failure).
    """
    # Step 1: Validate required params
    missing = [k for k, v in {
        "segment_id": segment_id,
        "channel": channel,
        "message_template": message_template,
        "campaign_name": campaign_name,
        "audience_sql": audience_sql,
    }.items() if not v]

    if missing:
        return {"error": f"Missing required parameters: {', '.join(missing)}"}

    pool = get_main_pool()
    readonly_pool = get_readonly_pool()

    # Step 2: Re-query audience
    try:
        async with readonly_pool.acquire() as conn:
            await conn.execute("SET statement_timeout = '10000'")
            # Strip safety/preview limits so we execute on the full segment
            exec_sql = re.sub(r"\bLIMIT\s+\d+\b", "", audience_sql, flags=re.IGNORECASE)
            audience_rows = await conn.fetch(exec_sql)
    except Exception as e:
        logger.error(f"[execute_campaign] Audience query failed: {e}")
        return {"error": f"Failed to query audience: {str(e)[:200]}"}

    if not audience_rows:
        return {"error": "No customers match this segment. Campaign not created."}

    customers = [_serialize_row(dict(r)) for r in audience_rows]

    # Step 3: Create campaign record
    try:
        campaign_id = await campaign_repo.create_campaign(
            pool=pool,
            name=campaign_name,
            segment_id=UUID(segment_id),
            channel=channel,
            message_template=message_template,
            total_audience=len(customers),
        )
    except Exception as e:
        logger.error(f"[execute_campaign] Campaign record creation failed: {e}")
        return {"error": f"Failed to create campaign record: {str(e)[:200]}"}

    # Step 4: Create communication records
    try:
        comm_ids = await campaign_repo.bulk_create_communications(
            pool=pool,
            campaign_id=campaign_id,
            customers=customers,
            channel=channel,
            message_template=message_template,
        )
    except Exception as e:
        logger.error(f"[execute_campaign] Communication creation failed: {e}")
        return {
            "error": f"Campaign created (ID: {campaign_id}) but communication records failed: {str(e)[:200]}",
            "campaign_id": str(campaign_id),
            "total_audience": len(customers),
            "communications_created": 0,
        }

    # Step 5: Queue for dispatch
    try:
        from app.services.redis_queue import push_to_queue
        push_to_queue("crm_dispatch_queue", {
            "campaign_id": str(campaign_id),
            "conversation_id": conversation_id
        })
    except Exception as e:
        logger.warning(f"[execute_campaign] Dispatch queue push failed (non-fatal): {e}")

    logger.info(
        f"[execute_campaign] Campaign '{campaign_name}' created. "
        f"ID={campaign_id}, audience={len(customers)}, comms={len(comm_ids)}."
    )
    return {
        "campaign_id": str(campaign_id),
        "total_audience": len(customers),
        "communications_created": len(comm_ids),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _serialize_row(row: dict) -> dict:
    """Convert a DB row dict to a JSON-serializable dict."""
    out = {}
    for key, value in row.items():
        if isinstance(value, UUID):
            out[key] = str(value)
        elif isinstance(value, Decimal):
            out[key] = float(value)
        elif hasattr(value, "isoformat"):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


async def _fetch_brand_profile_ctx() -> str:
    """
    Fetch the brand profile from the database and format it as a plain-text context string.
    Used as a fallback when brand_profile_ctx is not cached in state.
    """
    try:
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
                    f"  - {p.get('name')} | ₹{p.get('price')} | "
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
        logger.warning(f"[_fetch_brand_profile_ctx] Failed to fetch brand profile: {e}")
        return "No brand profile available."