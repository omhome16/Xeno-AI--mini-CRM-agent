"""
Database Schema — PostgreSQL table definitions.

6 core tables:
  - customers:       Customer profiles with aggregated metrics
  - orders:          Purchase history
  - segments:        Saved audience definitions (JSONB filter criteria)
  - campaigns:       Campaign definitions with denormalized counters
  - communications:  Individual message tracking per customer
  - delivery_events: Immutable event log for audit trail

Design decisions:
  - Denormalized counters on campaigns (total_sent, total_delivered, etc.)
    for fast dashboard reads without COUNT(*) on every page load
  - delivery_events with UNIQUE(idempotency_key) for atomic deduplication
  - Status hierarchy enforced at application level (forward-only transitions)
  - TEXT[] for tags — simple, queryable with ANY/&&, no join table needed

Note: asyncpg only supports single-statement execute(), so we run
each CREATE TABLE / CREATE INDEX as a separate statement.
"""

# Each statement is a separate string — asyncpg requires single-statement execution.
SCHEMA_STATEMENTS: list[str] = [
    # ════════════════════════════════════════════
    # CUSTOMERS
    # ════════════════════════════════════════════
    """
    CREATE TABLE IF NOT EXISTS customers (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        external_id     VARCHAR(255) UNIQUE,
        name            VARCHAR(255) NOT NULL,
        email           VARCHAR(255),
        phone           VARCHAR(50),
        whatsapp_id     VARCHAR(50),
        city            VARCHAR(100),
        tags            TEXT[] DEFAULT '{}',

        -- Denormalized aggregates (updated when orders are ingested)
        total_orders    INT DEFAULT 0,
        total_spent     DECIMAL(12,2) DEFAULT 0.00,
        avg_order_value DECIMAL(12,2) DEFAULT 0.00,
        last_order_at   TIMESTAMPTZ,
        first_order_at  TIMESTAMPTZ,

        created_at      TIMESTAMPTZ DEFAULT NOW(),
        updated_at      TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_customers_city ON customers(city)",
    "CREATE INDEX IF NOT EXISTS idx_customers_last_order ON customers(last_order_at)",
    "CREATE INDEX IF NOT EXISTS idx_customers_total_spent ON customers(total_spent)",
    "CREATE INDEX IF NOT EXISTS idx_customers_tags ON customers USING GIN(tags)",
    "CREATE INDEX IF NOT EXISTS idx_customers_external_id ON customers(external_id)",

    # ════════════════════════════════════════════
    # ORDERS
    # ════════════════════════════════════════════
    """
    CREATE TABLE IF NOT EXISTS orders (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
        order_date      TIMESTAMPTZ NOT NULL,
        total_amount    DECIMAL(12,2) NOT NULL,
        items_count     INT DEFAULT 1,
        status          VARCHAR(50) DEFAULT 'completed',
        created_at      TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date)",

    # ════════════════════════════════════════════
    # SEGMENTS
    # ════════════════════════════════════════════
    """
    CREATE TABLE IF NOT EXISTS segments (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name            VARCHAR(255) NOT NULL,
        description     TEXT,
        filter_criteria JSONB NOT NULL,
        customer_count  INT DEFAULT 0,
        created_at      TIMESTAMPTZ DEFAULT NOW(),
        updated_at      TIMESTAMPTZ DEFAULT NOW()
    )
    """,

    # ════════════════════════════════════════════
    # CAMPAIGNS
    # ════════════════════════════════════════════
    """
    CREATE TABLE IF NOT EXISTS campaigns (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name              VARCHAR(255) NOT NULL,
        segment_id        UUID REFERENCES segments(id),
        channel           VARCHAR(50) NOT NULL,
        message_template  TEXT NOT NULL,
        status            VARCHAR(50) DEFAULT 'draft',

        -- Denormalized counters for fast dashboard reads
        total_audience    INT DEFAULT 0,
        total_sent        INT DEFAULT 0,
        total_delivered   INT DEFAULT 0,
        total_failed      INT DEFAULT 0,
        total_opened      INT DEFAULT 0,
        total_clicked     INT DEFAULT 0,

        created_at        TIMESTAMPTZ DEFAULT NOW(),
        started_at        TIMESTAMPTZ,
        completed_at      TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_campaigns_status ON campaigns(status)",
    "CREATE INDEX IF NOT EXISTS idx_campaigns_created ON campaigns(created_at DESC)",

    # ════════════════════════════════════════════
    # COMMUNICATIONS (one per customer per campaign)
    # ════════════════════════════════════════════
    """
    CREATE TABLE IF NOT EXISTS communications (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
        customer_id     UUID NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
        channel         VARCHAR(50) NOT NULL,
        message_content TEXT NOT NULL,

        -- Delivery status (forward-only: pending -> sent -> delivered -> opened -> clicked)
        status          VARCHAR(50) DEFAULT 'pending',
        sent_at         TIMESTAMPTZ,
        delivered_at    TIMESTAMPTZ,
        failed_at       TIMESTAMPTZ,
        failure_reason  TEXT,
        opened_at       TIMESTAMPTZ,
        clicked_at      TIMESTAMPTZ,

        created_at      TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_comms_campaign ON communications(campaign_id)",
    "CREATE INDEX IF NOT EXISTS idx_comms_customer ON communications(customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_comms_status ON communications(status)",

    # ════════════════════════════════════════════
    # DELIVERY EVENTS (immutable audit log)
    # ════════════════════════════════════════════
    """
    CREATE TABLE IF NOT EXISTS delivery_events (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        communication_id  UUID NOT NULL REFERENCES communications(id) ON DELETE CASCADE,
        event_type        VARCHAR(50) NOT NULL,
        event_data        JSONB DEFAULT '{}',
        idempotency_key   VARCHAR(255) NOT NULL UNIQUE,
        created_at        TIMESTAMPTZ DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_events_comm ON delivery_events(communication_id)",
    "CREATE INDEX IF NOT EXISTS idx_events_type ON delivery_events(event_type)",

    # ════════════════════════════════════════════
    # READ-ONLY ROLE FOR AI QUERIES
    # ════════════════════════════════════════════
    """
    DO $$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'ai_reader') THEN
            CREATE ROLE ai_reader WITH LOGIN PASSWORD 'readonly';
        END IF;
    END $$
    """,
    "GRANT SELECT ON ALL TABLES IN SCHEMA public TO ai_reader",
]
