# 🤖 Xeno AI — Mini CRM Agent

An **AI-native Mini CRM** designed for Direct-to-Consumer (D2C) and retail brands, allowing marketers to plan, build, test, and execute personalized customer engagement campaigns through natural language conversation. The system features a **3-Phase Campaign Studio** (Brainstorm → Plan → Execute), safe database segmentation, real-time analytics dashboards, and an asynchronous, callback-driven delivery simulation layer.

---

## 🚀 Live Deployments

* **Frontend Web App**: [xeno-ai-mini-crm-agent.vercel.app](https://xeno-ai-mini-crm-agent.vercel.app/)
* **CRM Backend Service (Railway)**: [xeno-ai-mini-crm-agent-production.up.railway.app](https://xeno-ai-mini-crm-agent-production.up.railway.app)
* **Channel Simulator Service (Render)**: [xeno-ai-mini-crm-agent.onrender.com](https://xeno-ai-mini-crm-agent.onrender.com)

---

## 🏗️ High-Level System Architecture

The project consists of three decoupled components communicating via asynchronous queues and HTTP interfaces:

```mermaid
graph TD
    %% Frontend Layer
    subgraph Frontend_Layer ["Frontend UI"]
        UI["React + TypeScript App"]
    end

    %% CRM Backend Service
    subgraph CRM_Service ["CRM Backend Service (FastAPI)"]
        Agent["LangGraph Stateful Agent"]
        Gemini[("Google Gemini 2.5 Flash API")]
        Workers["Background Workers<br>(Dispatch & Receipt)"]
    end

    %% Redis State & Queues
    subgraph Redis_Backbone ["Redis Asynchronous Backbone"]
        Checkpoint[("LangGraph Checkpoint Store")]
        Queues[("Task Queues<br>(crm_dispatch_queue, crm_receipt_queue)")]
    end

    %% Database Layer
    subgraph PostgreSQL_DB ["PostgreSQL Database"]
        MainPool[("Main RW Pool<br>(campaigns, communications, orders)")]
        AIPool[("AI Read-Only Pool<br>(SELECT on customers, orders via 'ai_reader')")]
    end

    %% Channel Simulator
    subgraph Channel_Service ["Channel Simulator (FastAPI)"]
        Simulator["Simulated Funnel<br>(sent → delivered → opened → clicked → converted)"]
    end

    %% Connections
    UI <-->|HTTP / SSE Stream| CRM_Service
    Agent <-->|JSON Prompt / History| Gemini
    Agent <-->|Persists State| Checkpoint
    Workers <-->|Queue Jobs| Queues
    
    Workers -->|POST /api/send| Channel_Service
    Channel_Service -->|POST /api/receipts Webhooks| Workers
    
    Workers <-->|Write / Update| MainPool
    Agent <-->|Safe SELECT Queries (SQLGuard)| AIPool
```


* **React Frontend**: Built using TypeScript and styled with custom glassmorphism CSS. It handles the campaign chat interface, custom segment rules preview, and campaign statistics dashboards. It streams real-time agent thinking steps via Server-Sent Events (SSE) and polls campaign performance indicators automatically.
* **CRM Service (FastAPI)**: The central business logic orchestrator. It manages user chat sessions, segment calculations, message templates, campaigns, and delivery statuses. It hosts background threads that process Redis task queues asynchronously.
* **Channel Service (FastAPI)**: A stubbed messaging provider simulating channels (WhatsApp, SMS, Email, RCS). It accepts send dispatches, runs them through a probabilistic funnel, and issues webhook callbacks to the CRM Service to simulate delivery and conversion events.
* **Redis Connection**: Manages the message queues (`crm_dispatch_queue`, `crm_receipt_queue`, and `channel_simulation_queue`) and serves as the state checkpoint manager for LangGraph.
* **PostgreSQL Connection**: Stores records in 6 relational tables. Decoupled using two connection pools: a full-access main pool and a read-only SELECT-only pool.

---

## 🔄 End-to-End Campaign Lifecycle

The following diagram outlines the entire workflow of the application from the marketer's initial brainstorm to delivery simulation and webhook updates:

```mermaid
graph TD
    A[1. Marketer enters Chat Brief] --> B[2. AI extracts parameters & checks audience]
    B --> C[3. Marketer approves & launches Campaign]
    C --> D[4. CRM registers Segments & creates Communications]
    D --> E[5. CRM pushes dispatch job to Redis Queue]
    E --> F[6. Dispatch Worker sends requests to Channel Simulator]
    F --> G[7. Simulator processes events & hits Webhook API]
    G --> H[8. Receipt Worker updates Campaign Metrics & DB stats]
```

---

## ⚡ Core Workflows: Multi-Step Studio vs. Single-Prompt Creator

The platform supports two distinct design paradigms for campaign generation, tailoring the experience to the marketer's level of control and speed:

### 1. 🔄 Multi-Step Conversational Studio (Brainstorm → Plan → Execute)
This workflow is designed for marketers who want to co-pilot campaign details interactively, verifying segment attributes and message phrasing step-by-step.

```
 [ Brainstorm Chat ] ──► [ SQL Size Verification ] ──► [ Plan Dashboard ] ──► [ Approval & Launch ]
```

* **Phase 1: Brainstorm & Parameters Ingestion**
  The user enters the Campaign Studio chat. The AI Copilot uses the `COPILOT_INTENT_PROMPT` to analyze user inputs turn-by-turn. It extracts parameter fields (such as target city, tags like `'vip'`, minimal purchase order limits, specific channels, and promotional goals) and auto-saves them into a structured form layout.
* **Phase 2: Live Segment Calculation**
  As criteria are locked down, the agent calls the `query_customers_db` tool. The natural language parameters are compiled into SQL, checked by `SQLGuard` for safety, and executed on the read-only DB pool to display resulting audience counts dynamically to the marketer.
* **Phase 3: Plan Generation (`mode="plan"`)**
  When the essential brief parameters (Goal, Audience, Channel) are populated, the user clicks **Generate Campaign Plan**. The LangGraph agent executes nodes in `plan` mode. It compiles the SQL, registers the segment, drafts the target copy template with placeholders (`{{name}}`, `{{city}}`) using the brand profile styling rules, and displays a complete dashboard review. Crucially, a custom subgraph edge `_route_after_draft` terminates the graph without persisting a campaign database row—ensuring that planning drafts never commit duplicate campaign records or database errors.
* **Phase 4: Launch & Asynchronous Execution (`mode="execute"`)**
  The user can review, edit the message template, or run suggestions (Casual vs. Urgent vs. Formal styles). Once approved, the user clicks **Launch Campaign**. The graph runs in `execute` mode, creates the campaign database row (status `sending`), inserts the customer communications table records, and pushes a task to the Redis queue, immediately returning a success response while the background thread handles dispatching.

---

### 2. ⚡ Single-Prompt Autonomous Campaign Creator (One-Shot Mode)
For rapid, hands-off operation, the platform provides an autonomous interface. Rather than running a conversational wizard, a user specifies the entire campaign in a single natural language instruction:

> **Example Single Prompt**: *"Send an SMS welcome campaign to all customers in Delhi with a 15% discount on our Organic Cotton Crewneck using the code ECO15."*

```
 [ User One-Shot Prompt ] ──► [ Metadata Ingestion ] ──► [ Parameters Resolved? ]
                                                                   │
                                           ┌───────────────────────┴───────────────────────┐
                                      YES (Trigger Launch)                            NO (Clarification Chat)
                                           │                                               │
                                           ▼                                               ▼
                              [ Run Graph: Compile & Execute ]                   [ Prompt user for missing fields ]
```

* **Step 1: Database Metadata Ingestion**
  On invoking One-Shot Mode, the CRM fetches current database metadata—specifically active customer cities and existing tags in the PostgreSQL table—and feeds them directly into the `ONESHOT_COPILOT_PROMPT` as contextual data. This allows the model to match user inputs against real database states (e.g. spelling normalization: "delhi NCR" -> "Delhi").
* **Step 2: Unified Parameter Parsing**
  The LLM acts as an extraction parser. It analyzes the single prompt and maps it directly into the 4 required campaign pillars:
  1. `audience_description` (e.g. "customers in Delhi")
  2. `channel` (e.g. "sms")
  3. `offer_details` (e.g. "15% discount on Organic Cotton Crewneck")
  4. `message_description` (e.g. "Welcome campaign with discount code ECO15")
* **Step 3: Missing Fields Inspection**
  If any parameters are missing (e.g. if the user forgot the channel or offer details), the system suspends launch, sets `trigger_launch = false`, and returns a clarifying chat prompt listing the missing attributes (e.g. *"I've parsed the audience in Delhi and welcome offer, but which channel would you like to run this on?"*).
* **Step 4: Autonomous Compilation & Launch**
  Once all required parameters are resolved, the system sets `trigger_launch = true`, returns a confirmation reply, and launches the execution pipeline in the background. It generates the SQL query, registers the segment, creates the database campaign, writes the communications, and fires the Redis dispatch queue worker automatically. The user is taken directly to the live campaign stream dashboard.

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
  CREATE ROLE ai_reader WITH LOGIN PASSWORD 'AI_Reader_Secured_Pass_1029#';
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

### Truncating the Database
To completely clear all campaign execution logs, segments, customer profiles, and order data:
```bash
cd crm-service
# Activate virtual environment
python truncate_db.py [optional_DATABASE_URL]
```
This runs a utility that executes a `TRUNCATE ... CASCADE` on all data tables, returning the database to a clean, empty state.

### Reseeding the Database
To clear all data and automatically regenerate 1,500 new realistic Indian e-commerce customer profiles and ~5,000 order histories:
```bash
cd crm-service
# Activate virtual environment
python reseed_db.py
```
This runs a local generator that truncates the tables and seeds them with archetypes (VIP regular, active, lapsed, new). Alternatively, truncating the database and restarting the Railway backend triggers this seeder directly on the cloud server in under 45 seconds.