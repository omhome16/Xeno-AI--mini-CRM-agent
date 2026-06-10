"""
SQLGuard — Validates AI-generated SQL before execution.

Defense-in-depth for the hybrid query system:
  1. Parse SQL into AST (catches syntax errors)
  2. Verify it's a SELECT (blocks INSERT/UPDATE/DELETE/DROP)
  3. Check table allowlist (only customers, orders)
  4. Block multiple statements (no piggyback attacks)
  5. Block SQL comments (no bypass attempts)
  6. Auto-append LIMIT if missing (prevent full-table scans)

Combined with the read-only database connection pool, this provides
two independent layers of protection for AI-generated queries.
"""

import logging
from typing import Optional

import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)

# Tables the AI is allowed to query
ALLOWED_TABLES = {"customers", "orders"}

# Maximum rows returned from AI queries
MAX_LIMIT = 1000


class SQLGuardError(Exception):
    """Raised when AI-generated SQL fails validation."""
    pass


class SQLGuard:
    """
    Validates and sanitizes AI-generated SQL queries.

    Usage:
        guard = SQLGuard()
        safe_sql = guard.validate_and_prepare("SELECT * FROM customers WHERE city = 'Mumbai'")
        # safe_sql is guaranteed to be a safe SELECT with a LIMIT
    """

    def validate(self, sql: str) -> tuple[bool, str]:
        """
        Validate AI-generated SQL.

        Returns:
            (is_safe, reason) — True if safe, or False with rejection reason.
        """
        sql = sql.strip().rstrip(";")

        # ── Check 1: Block multiple statements ──
        if ";" in sql:
            return False, "Multiple statements not allowed"

        # ── Check 2: Block SQL comments (bypass vector) ──
        if "--" in sql or "/*" in sql:
            return False, "SQL comments not allowed"

        # ── Check 3: Parse into AST ──
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
        except sqlglot.errors.ParseError as e:
            return False, f"Invalid SQL syntax: {e}"

        # ── Check 4: Must be a SELECT ──
        if not isinstance(parsed, exp.Select):
            return False, f"Only SELECT statements allowed, got: {type(parsed).__name__}"

        # ── Check 5: Check referenced tables ──
        tables = set()
        for table in parsed.find_all(exp.Table):
            table_name = table.name.lower()
            if table_name:
                tables.add(table_name)

        # Also check subqueries and CTEs
        disallowed = tables - ALLOWED_TABLES
        if disallowed:
            return False, f"Query references disallowed tables: {disallowed}"

        # ── Check 6: Block dangerous expressions in subqueries ──
        dangerous_types = (
            exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create,
        )
        for node in parsed.walk():
            if isinstance(node, dangerous_types):
                return False, f"Dangerous operation found: {type(node).__name__}"

        return True, "OK"

    def add_limit(self, sql: str, max_limit: int = MAX_LIMIT) -> str:
        """
        Add a LIMIT clause if one doesn't already exist.
        Wraps the query in a subquery to enforce the limit.
        """
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
            if not parsed.find(exp.Limit):
                # Wrap in subquery with limit
                return f"SELECT * FROM ({sql.strip().rstrip(';')}) AS _q LIMIT {max_limit}"
        except Exception:
            pass  # If parsing fails here, the validate step would have caught it
        return sql

    def validate_and_prepare(self, sql: str) -> str:
        """
        Full pipeline: validate + add safety limits.

        Returns:
            Safe SQL string ready for execution.

        Raises:
            SQLGuardError: If the SQL fails validation.
        """
        is_safe, reason = self.validate(sql)
        if not is_safe:
            logger.warning(f"SQL rejected by SQLGuard: {reason} | SQL: {sql[:200]}")
            raise SQLGuardError(reason)

        safe_sql = self.add_limit(sql)
        logger.info(f"SQL approved by SQLGuard: {safe_sql[:200]}")
        return safe_sql
