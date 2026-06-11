# 🤖 Xeno AI — Mini CRM Agent

An **AI-native Mini CRM** that lets marketers create, plan, and execute personalized campaigns through natural conversation. The system features a structured **3-Phase Campaign Studio** (Brainstorm → Plan → Execute), real-time delivery event tracking, and database-aware customer segmentation.

---

## 🏗️ High-Level System Architecture

The project is built around a **three-service architecture** that decouples frontend client interactions, business logic, and communication providers:

```
┌─────────────────────────────────────────────────────────────┐
│                       REACT FRONTEND                        │
│             (Chat Studio UI & Performance Dashboard)         │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP Requests / SSE Stream
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                         CRM SERVICE                         │
│       (FastAPI Backend, LangGraph Stateful Orchestration)    │
└──────────────────┬───────────────────────┬──────────────────┘
                   │                       │
      PostgreSQL / │ Redis                 │ HTTP API
      Connection   │ Checkpoints           ▼
      Pools        ▼            ┌─────────────────────────────┐
┌─────────────────────────────┐ │       CHANNEL SERVICE       │
│         DATA STORES         │ │   (Communication Simulator) │
└─────────────────────────────┘ └──────────────┬──────────────┘
                                               │ Webhook Callbacks
                                               ▼
                                  (CRM Service Receipt API)
```

- **React Frontend**: A TypeScript-based single-page application that houses the campaign strategist chat interface and performance dashboard. It connects to the CRM service to submit messages and listens to live Server-Sent Events (SSE).
- **CRM Service**: The FastAPI backend orchestrator. It manages the databases, parses user intents, builds custom segments, drafts channel copy, and updates delivery funnel metrics.
- **Channel Service**: A standalone communication simulator. It exposes APIs to mock sending WhatsApp, Email, SMS, or RCS dispatches. Once triggered, it schedules asynchronous events in the background to post simulated delivery callbacks back to the CRM service.

---

## 🛠️ Architecture Choices & Technical Design Decisions

### 1. Stateful LangGraph Orchestration
Instead of running a linear pipeline, the agent's brain is modeled as a stateful graph using **LangGraph**.
- **State Checkpointing**: The graph's state is preserved in Redis after each node executes. This enables complete crash recovery and allows the backend to resume interrupted graphs safely.
- **Preview Re-routing Guard**: During the **Plan Review** phase, the graph executes in `plan` mode. We implement a conditional routing edge `_route_after_draft` that terminates the graph run before the `execute_campaign` node is reached. This guarantees that campaign rows are *never* pre-created in the database during planning, eliminating duplicate campaign errors.

### 2. LLM Strategy with Prioritized Model Cycling
To optimize for speed and reasoning depth, the backend uses Groq exclusively:
- **Groq LLM Client**: Utilized for intent parsing, SQL query building, segment rule compilation, and drafting channel marketing copy.
- **Resilient Fallback Pipeline**: If the primary Groq model throws rate limits (`429`) or errors, the backend automatically cycles through a prioritized pool of alternative models:
  1. `llama-3.3-70b-versatile`
  2. `llama-3.1-8b-instant`
  3. `mixtral-8x7b-32768`
  4. `gemma2-9b-it`
- **JSON Formatting Constraint Fallback**: Groq JSON mode requires the word "json" to be present in the prompt. If a model fails with a JSON validation error, the client retries the request without the JSON format constraint to ensure the agent never crashes.

### 3. Real-Time SSE Event Stream
To ensure a highly responsive UI, the frontend does not poll. It establishes a persistent Server-Sent Events (SSE) connection with the CRM service. Event frames include progress labels (e.g. `Generating SQL query`, `SQL executed`), query metadata, and finalized state outcomes, allowing the marketer to monitor the AI's step-by-step thinking.

---

## 📊 Database Schema Design

The CRM database is designed in **PostgreSQL** and uses targeted denormalization to ensure fast dashboard load times under intensive webhook callbacks.

```
┌───────────────────────────────────────────────────────────────────┐
│                             CUSTOMERS                             │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK)                                                     │
│ name (VARCHAR), email (VARCHAR), phone (VARCHAR)                  │
│ city (VARCHAR), tags (TEXT[] - e.g. {'vip', 'lapsed', 'new'})      │
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
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│                             SEGMENTS                              │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK), name (VARCHAR)                                     │
│ filter_criteria (JSONB - Reproducible criteria filters)           │
│ customer_count (INT)                                              │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ 1
                                  │
                                  │ 0..*
┌─────────────────────────────────▼─────────────────────────────────┐
│                             CAMPAIGNS                             │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK), segment_id (UUID, FK), name (VARCHAR)              │
│ channel (VARCHAR), message_template (TEXT)                        │
│ status (VARCHAR - 'sending', 'completed')                         │
│ sent_count (INT), delivered_count (INT), opened_count (INT)        │
│ clicked_count (INT) (Denormalized statistics for fast read)       │
└─────────────────────────────────┬─────────────────────────────────┘
                                  │ 1
                                  │
                                  │ 0..*
┌─────────────────────────────────▼─────────────────────────────────┐
│                          COMMUNICATIONS                           │
├───────────────────────────────────────────────────────────────────┤
│ id (UUID, PK), campaign_id (UUID, FK), customer_id (UUID, FK)     │
│ status (VARCHAR - 'sending', 'sent', 'delivered', 'failed')       │
│ clicked (BOOLEAN), opened (BOOLEAN)                               │
└───────────────────────────────────────────────────────────────────┘
```

### Key Schema Decisions
1. **Denormalized Campaign Counters**: Campaigns maintain running counters (`sent_count`, `delivered_count`, etc.). Instead of performing heavy table joins on hundreds of thousands of communications rows every time a dashboard page loads, statistics are updated incrementally in single database operations when callbacks fire.
2. **JSONB Filter Criteria**: Audience definitions are stored as a structured `JSONB` array of rules. This decoupling allows the agent to rerun the segment generation at any time to verify the latest matching audience size.
3. **Array Tags**: Customer attributes like `vip` or `lapsed` are stored in a standard PostgreSQL array column (`tags`), allowing simple, high-performance querying via `'vip' = ANY(tags)`.

---

## 🔄 AI Agent Lifecycle: Brainstorm → Plan → Execute

```
                  ┌────────────────────────────────┐
                  │   Phase 1: Brainstorm Chat     │
                  │   - Accumulate brief options   │
                  │   - ReAct database query loop  │
                  └───────────────┬────────────────┘
                                  │
                  All essential fields collected
                                  ▼
                  ┌────────────────────────────────┐
                  │     Phase 2: Plan Review       │
                  │   - SQLGuard validated query   │
                  │   - Edit copy templates        │
                  │   - Prevent duplicate creation │
                  └───────────────┬────────────────┘
                                  │
                           Launch clicked
                                  ▼
                  ┌────────────────────────────────┐
                  │   Phase 3: Autonomous Execute  │
                  │   - background dispatch workers    │
                  │   - channel service simulation │
                  │   - status callback loops      │
                  └────────────────────────────────┘
```

### Phase 1: Conversational Brainstorm
1. **Goal**: Assist the marketer in locking down campaign details (`goal`, `audience`, and `channel`).
2. **ReAct Query Loop**: When the user specifies a cohort (e.g. "VIPs in Delhi"), the agent triggers a ReAct loop. It drafts a secure SQL statement, passes it to **SQLGuard** to verify it is read-only, runs the query against the database, and injects the live customer counts into its response.
3. **Suggestion Filtering**: Suggestion chips are context-aware. The agent is restricted from mixing categories (e.g. it will never recommend channel chips during the audience selection step) and will never offer options for fields already present in the brief.
4. **Auto-Finish Check**: Once the brief collects all three essential parameters (`goal`, `audience`, and `channel`), the agent summarizes the setup, overrides/forces `ready_to_plan: true`, and serves exactly one suggestion chip: `{"label": "Generate Campaign Plan", "value": "plan_campaign", "category": "action"}`.

### Phase 2: Plan Review
1. **Action Trigger**: When the marketer clicks the `"Generate Campaign Plan"` chip, the frontend intercepts the action and calls `handlePlanCampaign()`, bypassing the chat submit logic.
2. **Sub-Graph Exit**: The graph is executed with `mode="plan"`. The `build_segment` node calculates the final audience count and generates a representative preview list. The `draft_message` node generates personalized marketing copy.
3. **Safety Re-Route**: The conditional edge `_route_after_draft` detects `mode="plan"` and routes the workflow directly to `END`, returning the plan data to the client without saving a campaign row in the database.

### Phase 3: Autonomous Execution
1. **Action Trigger**: The marketer reviews the plan (SQL, customer lists, copy) and clicks **Launch Campaign**.
2. **Database Persistence**: The graph runs with `mode="execute"`. It builds the segment database rows, creates a `campaign` row in `sending` status, and drafts the copy template.
3. **Background Worker Dispatch**: The node immediately spawns an asynchronous background task (`dispatch_campaign`) and returns a success response to the client.
4. **Mock Callback Loop**: The background task queries the target customer phone/whatsapp IDs and issues bulk send requests to the **Channel Service**. The Channel Service simulates sending, delivering, opening, and clicking with a delay, firing webhook callbacks back to the CRM's receipt endpoint, which increments the campaign's counters in real-time.

---

## 🚀 Quick Start Guide

### 1. Prerequisites
- Python 3.12+
- Node.js 18+
- Docker & Docker Compose

### 2. Setup Configuration
```bash
# Clone the repository
git clone https://github.com/omhome16/Xeno-AI--mini-CRM-agent.git
cd Xeno-AI--mini-CRM-agent

# Create environment template
cp .env.example .env
# Edit .env with your GROQ_API_KEY
```

### 3. Spin Up Infrastructure (PostgreSQL & Redis)
```bash
docker compose up -d
# Wait 10 seconds for DB and Redis to complete health checks
```

### 4. Start backend services
Open two separate terminals and launch the Python backend servers:

**Terminal 1 — CRM Service (Port 8000)**:
```bash
cd crm-service
python -m venv venv
# Activate virtualenv (Windows: .\venv\Scripts\activate, Linux/macOS: source venv/bin/activate)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Channel Service (Port 8001)**:
```bash
cd channel-service
python -m venv venv
# Activate virtualenv
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 5. Start the frontend
Open a third terminal and run the React client:

**Terminal 3 — React Client (Port 5173)**:
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.