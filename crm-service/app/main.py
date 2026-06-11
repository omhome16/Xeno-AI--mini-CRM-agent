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

        # 5. Start background workers
        import asyncio
        from app.workers.dispatch_worker import start_dispatch_worker
        from app.workers.receipt_worker import start_receipt_worker
        app.state.dispatch_worker_task = asyncio.create_task(start_dispatch_worker(), name="dispatch_worker")
        app.state.receipt_worker_task = asyncio.create_task(start_receipt_worker(), name="receipt_worker")
        logger.info("✓ Background queue workers started")

        logger.info(f"✓ {settings.APP_NAME} started successfully")

    except Exception as e:
        logger.error(f"✗ Startup failed: {e}")
        raise

    yield  # ← Application runs here

    # ── Shutdown ──
    logger.info(f"Shutting down {settings.APP_NAME}...")
    if hasattr(app.state, "dispatch_worker_task"):
        app.state.dispatch_worker_task.cancel()
    if hasattr(app.state, "receipt_worker_task"):
        app.state.receipt_worker_task.cancel()
    await close_db()
    logger.info("✓ Shutdown complete")


# ── Create FastAPI Application ──
import os
settings = get_settings()

# Export Langsmith variables to os.environ for LangChain / LangGraph automatic tracing
if settings.LANGSMITH_TRACING:
    os.environ["LANGSMITH_TRACING"] = settings.LANGSMITH_TRACING
if settings.LANGSMITH_ENDPOINT:
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
if settings.LANGSMITH_API_KEY:
    os.environ["LANGSMITH_API_KEY"] = settings.LANGSMITH_API_KEY
if settings.LANGSMITH_PROJECT:
    os.environ["LANGSMITH_PROJECT"] = settings.LANGSMITH_PROJECT

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
from app.routers.brand_router import router as brand_router
from app.routers.ingest_router import router as ingest_router

app.include_router(customer_router)
app.include_router(order_router)
app.include_router(receipt_router)
app.include_router(campaign_router)
app.include_router(chat_router)
app.include_router(brand_router)
app.include_router(ingest_router)
