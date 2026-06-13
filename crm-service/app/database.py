"""
Database connection management.

Manages two async connection pools:
  1. Main pool — full read/write access for application operations
  2. Read-only pool — restricted SELECT-only access for AI-generated SQL queries

The read-only pool is a defense-in-depth measure: even if the AI generates
a malicious query, the database role has no write permissions.
"""

import asyncpg
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Global connection pools (initialized on app startup)
_main_pool: Optional[asyncpg.Pool] = None
_readonly_pool: Optional[asyncpg.Pool] = None


async def init_db(database_url: str) -> asyncpg.Pool:
    """
    Initialize the main database connection pool.

    Args:
        database_url: PostgreSQL connection string.

    Returns:
        The asyncpg connection pool.
    """
    global _main_pool
    _main_pool = await asyncpg.create_pool(
        database_url,
        min_size=2,
        max_size=10,
        command_timeout=30,
        max_inactive_connection_lifetime=300.0,
    )
    logger.info("Main database pool initialized")
    return _main_pool


async def init_readonly_db(database_url: str) -> Optional[asyncpg.Pool]:
    """
    Initialize the read-only database connection pool for AI queries.

    This pool connects with the 'ai_reader' role which only has SELECT
    permissions. Falls back to the main pool if the read-only role
    doesn't exist yet (first startup).

    Args:
        database_url: PostgreSQL connection string (will be modified to use ai_reader).

    Returns:
        The read-only asyncpg connection pool, or None if setup fails.
    """
    global _readonly_pool
    try:
        # Replace credentials with read-only role
        # Format: postgresql://user:pass@host:port/db
        readonly_url = _build_readonly_url(database_url)
        _readonly_pool = await asyncpg.create_pool(
            readonly_url,
            min_size=1,
            max_size=5,
            command_timeout=5,  # Short timeout for AI queries
            max_inactive_connection_lifetime=300.0,
        )
        logger.info("Read-only database pool initialized")
        return _readonly_pool
    except Exception as e:
        logger.warning(
            f"Could not create read-only pool (will use main pool for AI queries): {e}"
        )
        return None


def get_main_pool() -> asyncpg.Pool:
    """Get the main database connection pool."""
    if _main_pool is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _main_pool


def get_readonly_pool() -> asyncpg.Pool:
    """
    Get the read-only pool for AI queries.
    Falls back to main pool if read-only pool is not available.
    """
    if _readonly_pool is not None:
        return _readonly_pool
    return get_main_pool()


async def close_db() -> None:
    """Close all database connection pools gracefully."""
    global _main_pool, _readonly_pool
    if _readonly_pool:
        await _readonly_pool.close()
        _readonly_pool = None
        logger.info("Read-only database pool closed")
    if _main_pool:
        await _main_pool.close()
        _main_pool = None
        logger.info("Main database pool closed")


def _build_readonly_url(database_url: str) -> str:
    """
    Transform a database URL to use the ai_reader role.

    Example:
        postgresql://postgres:postgres@localhost:5432/xeno_crm
        → postgresql://ai_reader:readonly@localhost:5432/xeno_crm
    """
    # Handle both postgresql:// and postgres:// schemes
    if "://" not in database_url:
        raise ValueError(f"Invalid database URL format: {database_url}")

    scheme, rest = database_url.split("://", 1)

    # Split user:pass@host from the rest
    if "@" in rest:
        _, host_and_db = rest.split("@", 1)
    else:
        host_and_db = rest

    return f"{scheme}://ai_reader:readonly@{host_and_db}"
