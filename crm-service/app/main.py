"""
Xeno AI CRM Service — Main Application Entry Point.

This is the core CRM backend that handles:
  - Customer and order data ingestion
  - AI agent chat interface (LangGraph + Gemini/Groq)
  - Campaign management and execution
  - Delivery receipt processing (idempotent callbacks)
  - Real-time analytics via SSE

Architecture:
  Routers → Services → Repositories → Database
  Each layer has a single responsibility and can be tested independently.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db, init_readonly_db, close_db

# ── Configure Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Application Lifespan ──
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown.

    Startup:
      1. Initialize database connection pools (main + read-only)
      2. Run schema migrations (CREATE IF NOT EXISTS)
      3. Seed demo data if database is empty
      4. Initialize Redis connection

    Shutdown:
      1. Close database pools
      2. Close Redis connection
    """
    settings = get_settings()
    logger.info(f"Starting {settings.APP_NAME}...")

    # ── Startup ──
    try:
        # 1. Database pools
        pool = await init_db(settings.DATABASE_URL)
        logger.info("✓ Main database pool ready")

        # 2. Read-only pool for AI queries (non-critical, may fail on first run)
        await init_readonly_db(settings.DATABASE_URL)
        logger.info("✓ Read-only database pool ready")

        # 3. Schema migration (each statement executed individually — asyncpg requirement)
        from app.schema import SCHEMA_STATEMENTS
        async with pool.acquire() as conn:
            for stmt in SCHEMA_STATEMENTS:
                await conn.execute(stmt)
        logger.info("✓ Database schema migrated")

        # 4. Seed demo data if database is empty
        async with pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM customers")
        if count == 0:
            from app.seed.seeder import seed_demo_data
            summary = await seed_demo_data(pool)
            logger.info(f"✓ Seeded demo data: {summary}")
        else:
            logger.info(f"✓ Database already has {count} customers — skipping seed")

        # 5. Redis will be added in Phase 7
        # app.state.redis = Redis.from_url(settings.REDIS_URL)

        logger.info(f"✓ {settings.APP_NAME} started successfully")

    except Exception as e:
        logger.error(f"✗ Startup failed: {e}")
        raise

    yield  # ← Application runs here

    # ── Shutdown ──
    logger.info(f"Shutting down {settings.APP_NAME}...")
    await close_db()
    logger.info("✓ Shutdown complete")


# ── Create FastAPI Application ──
settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-native Mini CRM for intelligent customer engagement",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS Middleware ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",  # Fallback
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health Check ──
@app.get("/health", tags=["System"])
async def health_check():
    """
    Health check endpoint for deployment monitoring.
    Returns service status and version info.
    """
    return {
        "status": "healthy",
        "service": "crm-service",
        "version": "0.1.0",
    }


# ── API Root ──
@app.get("/", tags=["System"])
async def root():
    """API root — service information."""
    return {
        "service": settings.APP_NAME,
        "version": "0.1.0",
        "docs": "/docs",
        "health": "/health",
    }


# ── Register Routers ──
from app.routers.customer_router import router as customer_router
from app.routers.order_router import router as order_router
from app.routers.receipt_router import router as receipt_router
from app.routers.campaign_router import router as campaign_router
from app.routers.chat_router import router as chat_router

app.include_router(customer_router)
app.include_router(order_router)
app.include_router(receipt_router)
app.include_router(campaign_router)
app.include_router(chat_router)
