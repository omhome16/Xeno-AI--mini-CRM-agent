# 🤖 Xeno AI — Mini CRM Agent

An **AI-native Mini CRM** designed for Direct-to-Consumer (D2C) and retail brands, allowing marketers to plan, build, test, and execute personalized customer engagement campaigns through natural language conversation. The system features a **3-Phase Campaign Studio** (Brainstorm → Plan → Execute), safe database segmentation, real-time analytics dashboards, and an asynchronous, callback-driven delivery simulation layer.

---

## 🏗️ High-Level System Architecture

The project consists of three decoupled components communicating via asynchronous queues and HTTP interfaces:

```mermaid
graph TD
    subgraph Frontend [React TypeScript Client]
        UI[Glassmorphism Chat & Dashboard UI]
    end

    subgraph CRM_Backend [CRM Service FastAPI]
        Router[FastAPI Routers]
        LangGraphAgent[LangGraph Campaign Graph]
        SQLG[SQLGuard AST Security Guard]
        MainPool[(Main PG Pool - RW)]
        ROPool[(Read-only PG Pool - RO)]
        DispatchWorker[Campaign Dispatch Worker]
        ReceiptWorker[Callback Receipt Worker]
    end

    subgraph Channel_Simulator [Channel Service FastAPI]
        ChanRouter[Send API Router]
        SimWorker[Simulation Worker]
        ProbModel[Lifecycle Funnel Simulator]
    end

    subgraph Data_Stores [Cache & Database]
        PG[(PostgreSQL DB)]
        Redis[(Redis Cache & Queues)]
    end

    subgraph LLM_Provider [Google Gemini API]
        Gemini[Gemini 2.5 Flash]
    end

    %% Network / API Connections
    UI -->|HTTP / SSE Stream| Router
    Router --> LangGraphAgent
    LangGraphAgent -->|1. SQL Generation| Gemini
    LangGraphAgent -->|2. AST Validation| SQLG
    LangGraphAgent -->|3. Segment Size Verification| ROPool
    ROPool --> PG
    LangGraphAgent -->|4. Persist Segment & Campaign| MainPool
    MainPool --> PG

    %% Asynchronous Pipelines
    LangGraphAgent -->|Queue Campaign| Redis
    Redis -.->|Pop Task| DispatchWorker
    DispatchWorker -->|HTTP POST /api/send| ChanRouter
    ChanRouter -->|Queue Simulation| Redis
    Redis -.->|Pop Simulation Job| SimWorker
    SimWorker --> ProbModel
    ProbModel -->|Webhook Callbacks| Router
    Router -->|Queue Receipt| Redis
    Redis -.->|Pop Batch Receipts| ReceiptWorker
    ReceiptWorker -->|Update Metrics & Customer CLV| MainPool
```

* **React Frontend**: Built using TypeScript and styled with custom glassmorphism CSS. It handles the campaign chat interface, custom segment rules preview, and campaign statistics dashboards. It streams real-time agent thinking steps via Server-Sent Events (SSE) and polls campaign performance indicators automatically.
* **CRM Service (FastAPI)**: The central business logic orchestrator. It manages user chat sessions, segment calculations, message templates, campaigns, and delivery statuses. It hosts background threads that process Redis task queues asynchronously.
* **Channel Service (FastAPI)**: A stubbed messaging provider simulating channels (WhatsApp, SMS, Email, RCS). It accepts send dispatches, runs them through a probabilistic funnel, and issues webhook callbacks to the CRM Service to simulate delivery and conversion events.
* **Redis Connection**: Manages the message queues (`crm_dispatch_queue`, `crm_receipt_queue`, and `channel_simulation_queue`) and serves as the state checkpoint manager for LangGraph.
* **PostgreSQL Connection**: Stores records in 6 relational tables. Decoupled using two connection pools: a full-access main pool and a read-only SELECT-only pool.

---

## 🔄 End-to-End Campaign Lifecycle

The following sequence diagram outlines the entire workflow of the application from the marketer's initial brainstorm to delivery simulation and webhook updates:

```mermaid
sequenceDiagram
    autonumber
    actor Marketer
    participant UI as React Client
    participant CRM as CRM Service
    participant Gemini as Gemini 2.5 Flash
    participant DB as PostgreSQL
    participant Redis as Redis Queues
    participant CS as Channel Service

    Marketer->>UI: Input prompt / Chat in Copilot
    UI->>CRM: POST /api/chat (copilot or oneshot)
    CRM->>Gemini: Extract campaign parameters from chat
    Gemini-->>CRM: Extracted brief updates (channel, audience, goal)
    CRM-->>UI: Live brief state & action suggestions (SSE)
    
    Note over Marketer, UI: When brief has Goal, Audience, and Channel:
    
    Marketer->>UI: Click "Generate Campaign Plan"
    UI->>CRM: POST /api/chat/plan
    CRM->>Gemini: Generate SQL query from NL description
    Gemini-->>CRM: SQL SELECT query
    CRM->>CRM: SQLGuard: Verify safety (AST) & append LIMIT
    CRM->>DB: Execute query via Read-Only Pool (ai_reader)
    DB-->>CRM: Total customer counts & preview records
    CRM->>Gemini: Generate personalized message template
    Gemini-->>CRM: Draft text (e.g. Hello {{name}}...)
    CRM-->>UI: Return plan preview (count, SQL, message template)
    
    Marketer->>UI: Click "Launch Campaign" (Confirm)
    UI->>CRM: POST /api/chat/execute
    CRM->>DB: Save Segment & Campaign (status = 'sending')
    CRM->>DB: Create individual Communication records (status = 'pending')
    CRM->>Redis: Push campaign_id to crm_dispatch_queue
    CRM-->>UI: Return 202 Accepted (runs asynchronously)

    Note over CRM, Redis: Background Dispatch Thread
    Redis->>CRM: Pop campaign_id from crm_dispatch_queue (dispatch_worker)
    loop For each customer communication
        CRM->>CS: POST /api/send (communication_id, recipient, message)
        CS->>Redis: Push to channel_simulation_queue
        CS-->>CRM: 202 Accepted
    end
    CRM->>DB: Update Campaign status = 'completed' (dispatch finished)

    Note over CS, Redis: Background Simulation Thread
    CS->>CS: simulation_worker pops from channel_simulation_queue
    loop Probabilistic Funnel Simulation
        CS->>CS: Sent (100% prob) - Delay 0.1-0.5s
        CS->>CRM: Webhook POST /api/receipts (status = 'sent')
        CS->>CS: Delivered (90% prob) / Failed (10% prob) - Delay 0.5-3.0s
        CS->>CRM: Webhook POST /api/receipts (status = 'delivered' or 'failed')
        CS->>CS: Opened (60% of delivered) - Delay 2-15s
        CS->>CRM: Webhook POST /api/receipts (status = 'opened')
        CS->>CS: Clicked (30% of opened) - Delay 1-10s
        CS->>CRM: Webhook POST /api/receipts (status = 'clicked')
        CS->>CS: Converted (10% of clicked) - Delay 0.5-3.0s
        CS->>CRM: Webhook POST /api/receipts (status = 'converted', revenue, product, category)
    end

    Note over CRM, Redis: Webhook Receipt Ingestion & Processing
    CRM->>Redis: process_receipt pushes to crm_receipt_queue
    Redis->>CRM: Pop batch (up to 50) of receipts (receipt_worker)
    loop Each receipt in batch
        CRM->>DB: Insert event into delivery_events (ON CONFLICT DO NOTHING)
        Note over CRM, DB: Enforces idempotency via uniqueness key
        alt Valid state transition
            CRM->>DB: Update communication status (forward-only order)
            CRM->>DB: Update Campaign denormalized statistics counter (+1)
            opt Event is 'converted'
                CRM->>DB: Create Order record (status = 'completed')
                CRM->>DB: Recompute Customer totals (spent, orders, last_order_at)
            end
        end
    end
```

---

## 🧠 LangGraph Orchestration & Agent Workflow

The campaign strategist brain is modeled as a stateful graph using **LangGraph**, enabling structured steps, tool execution, and contextual fallbacks.

```
          START ──► setup_campaign_state ──► agent_loop ◄───► call_tool
                                                 │ (tool_to_call == null)
                                                 ▼
                                                END
```

### 1. The Campaign State (`CampaignState`)
The graph passes a typed dictionary containing:
* **Inputs**: `user_message`, `mode` (`"brainstorm" | "plan" | "execute"`), and `conversation_id`.
* **Brief**: `goal`, `audience`, `channel`, `message_idea`, and `offer`.
* **Segment**: `audience_sql`, `audience_count`, `audience_preview`, and `segment_id`.
* **Drafts**: `message_template` and `message_char_count`.
* **Execution**: `campaign_id` and `communications_created`.
* **Scratchpad**: `think_pad` (thinking trail), `tool_to_call`, `tool_args`, and `last_tool_output`.

### 2. Graph Nodes
* **`setup_campaign_state`**: Deterministically initializes variables and retrieves the active brand profile context from the database to inject into the session.
* **`agent_loop`**: Invokes Gemini 2.5 Flash to decide whether to call a tool or output a text response. It formats system prompts dynamically, cleans LLM syntax, and parses output JSON fields securely.
* **`call_tool`**: Maps tool requests to python functions and updates state metrics.

### 3. Tool Catalog
* **`query_customers_db`**: Translates segment descriptions into SQL queries, executes them on the read-only pool, and returns a count and sample row preview.
* **`create_saved_segment`**: Extracts structured criteria and saves segment definitions into PostgreSQL.
* **`draft_marketing_message`**: Generates customized copy templates with placeholders (e.g. `{{name}}`, `{{city}}`) matching the brand's tone of voice and active catalogs.
* **`execute_saved_campaign`**: Persists campaign metadata, creates individual communications for all segment members, and queues the task for background dispatch.

---

## 🛡️ SQLGuard: AI Query Defense System

To let AI generate raw SQL queries safely, the system implements a **dual-layer defense-in-depth model**:

```
[ AI SQL Generation ] ──► [ SQLGuard AST Parser ] ──► [ SELECT-Only Connection Pool ] ──► [ DB ]
```

### Layer 1: SQLGuard AST Validator (`sqlglot`)
Before executing any AI-generated SQL query, it is validated programmatically:
1. **Multi-Statement Rejection**: Rejects queries containing semicolons (`;`) to block piggybacked query injections.
2. **Comment Disallowing**: Rejects queries with `--` or `/*` to prevent comment-based filter bypasses.
3. **AST Check**: Parses the query into an Abstract Syntax Tree (AST) using `sqlglot`. Verifies the query type is exactly `sqlglot.exp.Select`.
4. **Table Allowlist**: Checks that the query only references allowed tables (`customers` and `orders`). Any references to database catalog tables, schema settings, or segments are blocked.
5. **Operation Block**: Verifies that no subqueries contain modifying instructions like `INSERT`, `UPDATE`, `DELETE`, `CREATE`, or `DROP`.
6. **Limit Injection**: Wraps the final validated query inside a subquery to apply a strict row count ceiling (`LIMIT 1000`), protecting memory and preventing database read starvation.

### Layer 2: Read-Only Database Role (`ai_reader`)
Even if SQLGuard is bypassed, the database itself enforces security:
* The read-only connection pool connects to PostgreSQL using the **`ai_reader`** role.
* This role is explicitly granted only `SELECT` privileges:
  ```sql
  CREATE ROLE ai_reader WITH LOGIN PASSWORD 'readonly';
  GRANT SELECT ON ALL TABLES IN SCHEMA public TO ai_reader;
  ```
* Any write or modification attempts will be blocked by PostgreSQL's permission model.

---

## 📊 Database Schema Design

The CRM database is implemented in **PostgreSQL** with targeted denormalization to ensure analytics dashboards render instantly.

```
┌───────────────────────────────────────────────────────────────────┐
│                             CUSTOMERS                             │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK)                                                     │
│ external_id (VARCHAR, UNIQUE)                                     │
│ name (VARCHAR), email (VARCHAR), phone (VARCHAR), whatsapp_id (VC)│
│ city (VARCHAR), tags (TEXT[] - e.g. {'vip', 'lapsed', 'regular'})  │
│ total_orders (INT), total_spent (DECIMAL), avg_order_value (DEC)  │
│ last_order_at (TIMESTAMPTZ), first_order_at (TIMESTAMPTZ)          │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ 1
                                  │
                                  │ 0..*
┌─────────────────────────────────▼─────────────────────────────────┐
│                              ORDERS                               │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK), customer_id (UUID, FK)                             │
│ order_date (TIMESTAMPTZ), total_amount (DECIMAL), status (VARCHAR)│
│ items_count (INT), category (VARCHAR), product_name (VARCHAR)     │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│                             SEGMENTS                              │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK), name (VARCHAR), description (TEXT)                 │
│ filter_criteria (JSONB - Repositories filter rules)               │
│ customer_count (INT)                                              │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ 1
                                  │
                                  │ 0..*
┌─────────────────────────────────▼─────────────────────────────────┐
│                             CAMPAIGNS                             │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK), segment_id (UUID, FK), name (VARCHAR)              │
│ channel (VARCHAR), message_template (TEXT), status (VARCHAR)      │
│ total_audience (INT), total_sent (INT), total_delivered (INT)     │
│ total_failed (INT), total_opened (INT), total_clicked (INT)       │
│ total_conversions (INT), total_attributed_revenue (DECIMAL)       │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ 1
                                  │
                                  │ 0..*
┌─────────────────────────────────▼─────────────────────────────────┐
│                          COMMUNICATIONS                           │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK), campaign_id (UUID, FK), customer_id (UUID, FK)     │
│ status (VARCHAR - 'pending', 'sent', 'delivered', 'failed', etc.) │
│ message_content (TEXT), failure_reason (TEXT)                     │
│ sent_at, delivered_at, failed_at, opened_at, clicked_at, conv_at   │
│ attributed_revenue (DECIMAL)                                      │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ 1
                                  │
                                  │ 0..*
┌─────────────────────────────────▼─────────────────────────────────┐
│                          DELIVERY EVENTS                          │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK), communication_id (UUID, FK)                        │
│ event_type (VARCHAR), event_data (JSONB)                          │
│ idempotency_key (VARCHAR, UNIQUE)                                 │
└───────────────────────────────────────────────────────────────────┘
```

### Key Design Details
1. **Denormalized Campaign Statistics**: The `campaigns` table stores running aggregates (`total_sent`, `total_conversions`, etc.). Webhook callbacks increment these counters in single operations rather than forcing heavy SQL `COUNT` queries on every dashboard read.
2. **Text Arrays (`tags`)**: Customer attributes like `vip` or `lapsed` are stored in a native PostgreSQL text array (`tags`), queryable using the indexing benefits of `GIN` arrays (e.g. `tags @> ARRAY['vip']`), removing the overhead of join tables.
3. **Idempotency Log (`delivery_events`)**: Maintains an audit log of callbacks. The database guarantees that duplicate updates from the channel simulator are ignored via a unique key: `ON CONFLICT (idempotency_key) DO NOTHING`.

---

## ⚡ Asynchronous Redis Queue Pipeline

To protect the services from network delays and connection exhaustion during high-volume sends or webhook callback spikes, all heavy IO is decoupled using Redis queues:

```
[ CRM Ingestion Router ] ──► (rpush) ──► [ Redis crm_receipt_queue ] ──► (blpop) ──► [ Receipt Worker Threads ]
```

### 1. Campaign Dispatch Pipeline (`crm_dispatch_queue`)
* When execution is triggered, the agent inserts communications into the DB and pushes the `campaign_id` to `crm_dispatch_queue`.
* The `dispatch_worker` picks it up and calls the Channel Service in batches of `50` messages (with a delay of `0.5s` to throttle outbound requests).
* SSE events are pushed back to the client to update delivery progress percentages.

### 2. Callback Ingestion Pipeline (`crm_receipt_queue`)
* Webhooks hit the `/api/receipts` endpoint on the CRM Service.
* The router serializes the payload, issues a Redis `RPUSH` to `crm_receipt_queue`, and returns a `202 Accepted` status within milliseconds.
* The background `receipt_worker` polls the queue:
  * Uses a blocking `BLPOP` to catch active payloads.
  * Dynamically queries a batch of up to `49` additional items using `LPOP` to process events in groups.
  * Wraps updates in individual database savepoint transactions. If one receipt in the batch fails due to data anomalies, the rest are still committed.
  * Enforces a forward-only lifecycle status rule: `pending` → `sent` → `delivered` → `opened` → `clicked` → `converted`. Out-of-order webhooks are discarded.
  * **Attribution & Customer CLV**: During `converted` events, the worker extracts the order values and matches the product against the brand's product catalog. It inserts a completed order record, aggregates customer totals (`total_spent`, `total_orders`), and updates campaign conversion metrics.

---

## ⚙️ Local Development Setup

### 1. Prerequisites
Ensure you have the following installed on your local machine:
* Python 3.12+
* Node.js 18+
* Docker & Docker Compose

### 2. Configure Environment Variables
Create a root `.env` file containing configuration keys for your services:
```bash
# Clone the repository
git clone https://github.com/omhome16/Xeno-AI--mini-CRM-agent.git
cd Xeno-AI--mini-CRM-agent

# Create environment template
cp .env.example .env
```
Ensure your `.env` contains your Gemini API key:
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5433/xeno_crm
REDIS_URL=redis://localhost:6379
GEMINI_API_KEY=your_gemini_api_key_here
SEED_DEMO_DATA=True
CHANNEL_SERVICE_URL=http://localhost:8001/api/send
FRONTEND_URL=http://localhost:5173
APP_NAME="Xeno AI CRM"
```

### 3. Start Database and Redis
Spin up the PostgreSQL and Redis containers:
```bash
docker compose up -d
```
*Wait 10 seconds for the database and Redis to complete health checks and open connections.*

### 4. Launch Backend Services
The backend is split into two Python services. Start them in separate terminals:

#### Terminal 1 — CRM Service (Port 8000)
```bash
cd crm-service
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
*On startup, the CRM Service automatically creates the database schema, seeds the database with demo customers and store outlets, triggers customer tag synchronization, and launches the queue workers.*

#### Terminal 2 — Channel Service (Port 8001)
```bash
cd channel-service
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 5. Launch React Frontend (Port 5173)
Start the client application in a third terminal:

#### Terminal 3 — React Client
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser to access the application.

---

## 🛠️ Diagnostics & Maintenance

### Reseeding the Database
To clear all data, resector campaigns, and reset the customer metrics to a clean, fresh state:
```bash
cd crm-service
# Activate virtual environment
python reseed_db.py
```
This runs a secure utility that truncates all tables except the brand profiles, maps customer order history, recalculates aggregates, and syncs tag structures.