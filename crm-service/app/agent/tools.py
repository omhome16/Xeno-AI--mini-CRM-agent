"""
Agent Tools — Functions the LangGraph agent can invoke.

Each tool is a standalone async function that interacts with the
database or LLM to accomplish a specific task within the campaign
creation workflow.

Tools:
  - query_customers: Execute AI-generated SQL against the database
  - create_segment: Save a segment definition with JSONB filter
  - generate_message: Draft a channel-appropriate marketing message
  - send_campaign: Execute the campaign (create records + dispatch to channel service)
"""

import json
import logging
from typing import Any
from uuid import UUID

from langsmith import traceable

from app.database import get_main_pool, get_readonly_pool
from app.services.sql_guard import SQLGuard, SQLGuardError
from app.agent.prompts import (
    SQL_GENERATION_PROMPT,
    FILTER_GENERATION_PROMPT,
    MESSAGE_GENERATION_PROMPT,
    CAMPAIGN_NAMING_PROMPT,
)
from app.repositories import campaign_repo, customer_repo

logger = logging.getLogger(__name__)

_sql_guard = SQLGuard()


@traceable(run_type="tool")
async def query_customers(llm_client, audience_description: str) -> dict:
    """
    Convert natural language to SQL, validate, and execute.

    Flow:
      1. LLM generates SQL from natural language
      2. SQLGuard validates and adds LIMIT
      3. Execute against read-only connection pool
      4. Return results with the SQL used

    Args:
        llm_client: The DualLLMClient instance.
        audience_description: Natural language description of target audience.

    Returns:
        Dict with sql, results, count, total_count.
    """
    # Step 1: Generate SQL via LLM
    raw_sql = await llm_client.reason(
        system_prompt=SQL_GENERATION_PROMPT,
        user_input=audience_description,
    )

    # Clean up LLM response (sometimes wraps in code fences)
    sql = raw_sql.strip()
    if sql.startswith("```"):
        sql = sql.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    sql = sql.rstrip(";")

    # Step 2: Validate with SQLGuard
    try:
        safe_sql = _sql_guard.validate_and_prepare(sql)
    except SQLGuardError as e:
        return {
            "error": f"Generated SQL was rejected: {e}",
            "sql": sql,
            "results": [],
            "count": 0,
        }

    # Step 3: Execute against read-only pool
    readonly_pool = get_readonly_pool()
    try:
        async with readonly_pool.acquire() as conn:
            await conn.execute("SET statement_timeout = '5000'")
            rows = await conn.fetch(safe_sql)

            # Step 3b: Get the TRUE total count (without LIMIT)
            # Wrap the base query (without LIMIT/ORDER) in COUNT(*)
            import re
            count_sql = safe_sql
            # Remove LIMIT clause
            count_sql = re.sub(r'\s+LIMIT\s+\d+', '', count_sql, flags=re.IGNORECASE)
            # Remove ORDER BY clause
            count_sql = re.sub(r'\s+ORDER\s+BY\s+[\w.,\s]+(?:ASC|DESC)?', '', count_sql, flags=re.IGNORECASE)
            count_sql = f"SELECT COUNT(*) as total FROM ({count_sql}) _sub"
            try:
                total_row = await conn.fetchrow(count_sql)
                total_count = total_row["total"] if total_row else len(rows)
            except Exception:
                total_count = len(rows)

    except Exception as e:
        logger.error(f"SQL execution failed: {e}")
        return {
            "error": f"Query execution failed: {str(e)[:200]}",
            "sql": safe_sql,
            "results": [],
            "count": 0,
        }

    # Convert to serializable format
    from decimal import Decimal
    results = []
    for row in rows:
        record = {}
        for key, value in dict(row).items():
            if isinstance(value, UUID):
                record[key] = str(value)
            elif isinstance(value, Decimal):
                record[key] = float(value)
            elif hasattr(value, "isoformat"):
                record[key] = value.isoformat()
            else:
                record[key] = value
        results.append(record)

    return {
        "sql": safe_sql,
        "results": results,  # Return ALL fetched rows for preview
        "count": total_count,  # TRUE total, not limited by LIMIT
    }


@traceable(run_type="tool")
async def create_segment(
    llm_client,
    audience_description: str,
    customer_count: int,
) -> dict:
    """
    Create and save a segment with JSONB filter criteria.

    Flow:
      1. LLM generates JSONB filter from natural language
      2. Save to segments table
      3. Return segment ID and filter

    Args:
        llm_client: The DualLLMClient instance.
        audience_description: Description of the audience.
        customer_count: Number of customers matching this segment.

    Returns:
        Dict with segment_id, name, filter_criteria.
    """
    pool = get_main_pool()

    # Generate JSONB filter
    filter_json = await llm_client.reason(
        system_prompt=FILTER_GENERATION_PROMPT,
        user_input=audience_description,
    )

    # Parse filter JSON
    try:
        filter_text = filter_json.strip()
        if filter_text.startswith("```"):
            filter_text = filter_text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        filter_criteria = json.loads(filter_text)
    except json.JSONDecodeError:
        filter_criteria = {"filters": [{"field": "all", "op": "eq", "value": True}]}
        logger.warning(f"Failed to parse filter JSON, using fallback: {filter_json[:200]}")

    # Generate segment name
    name = await llm_client.generate(
        system_prompt=CAMPAIGN_NAMING_PROMPT,
        user_input=f"Audience: {audience_description}",
    )
    name = name.strip().strip('"')[:100]

    # Save segment
    segment_id = await campaign_repo.create_segment(
        pool=pool,
        name=name,
        description=audience_description,
        filter_criteria=filter_criteria,
        customer_count=customer_count,
    )

    return {
        "segment_id": str(segment_id),
        "name": name,
        "filter_criteria": filter_criteria,
        "customer_count": customer_count,
    }


@traceable(run_type="tool")
async def generate_message(
    llm_client,
    channel: str,
    audience_description: str,
    message_description: str,
    offer_details: str = "",
) -> dict:
    """
    Draft a channel-appropriate marketing message.

    Args:
        llm_client: The DualLLMClient instance.
        channel: Channel type (whatsapp, sms, email, rcs).
        audience_description: Who the message is for.
        message_description: What the message should say.
        offer_details: Specific offer/discount details.

    Returns:
        Dict with message_template, channel, char_count.
    """
    context = (
        f"Channel: {channel}\n"
        f"Audience: {audience_description}\n"
        f"Message goal: {message_description}\n"
        f"Offer details: {offer_details or 'None specified'}"
    )

    # Load and format brand profile dynamic context
    from app.repositories import brand_repo
    pool = get_main_pool()
    profile = await brand_repo.get_brand_profile(pool)
    brand_profile_ctx = "No brand profile configured. General retail brand context applies."
    if profile:
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
        brand_profile_ctx = "\n".join(context_lines)

    sys_prompt = MESSAGE_GENERATION_PROMPT.replace("{context}", context).replace("{brand_profile}", brand_profile_ctx)

    message = await llm_client.generate(
        system_prompt=sys_prompt,
        user_input=context,
    )

    message = message.strip()

    return {
        "message_template": message,
        "channel": channel,
        "char_count": len(message),
    }


@traceable(run_type="tool")
async def execute_campaign(
    llm_client,
    segment_id: str,
    channel: str,
    message_template: str,
    campaign_name: str,
    audience_sql: str,
) -> dict:
    """
    Execute a campaign — create records and dispatch to channel service.

    Flow:
      1. Re-query audience using the saved SQL
      2. Create campaign record
      3. Create communication records for each customer
      4. Return campaign_id (dispatch handled by worker in Phase 9)

    Args:
        Various campaign parameters.

    Returns:
        Dict with campaign_id, total_audience.
    """
    pool = get_main_pool()
    readonly_pool = get_readonly_pool()

    # Re-query to get current audience
    try:
        async with readonly_pool.acquire() as conn:
            await conn.execute("SET statement_timeout = '5000'")
            audience_rows = await conn.fetch(audience_sql)
    except Exception as e:
        return {"error": f"Failed to query audience: {e}"}

    if not audience_rows:
        return {"error": "No customers match this segment"}

    customers = [dict(r) for r in audience_rows]

    # Create campaign
    campaign_id = await campaign_repo.create_campaign(
        pool=pool,
        name=campaign_name,
        segment_id=UUID(segment_id),
        channel=channel,
        message_template=message_template,
        total_audience=len(customers),
    )

    # Create communication records
    comm_ids = await campaign_repo.bulk_create_communications(
        pool=pool,
        campaign_id=campaign_id,
        customers=customers,
        channel=channel,
        message_template=message_template,
    )

    return {
        "campaign_id": str(campaign_id),
        "total_audience": len(customers),
        "communications_created": len(comm_ids),
    }
