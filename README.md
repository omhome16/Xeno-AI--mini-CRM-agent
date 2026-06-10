# 🤖 Xeno AI — Mini CRM Agent

An **AI-native Mini CRM** that lets marketers create and execute personalized campaigns through natural conversation. Built with a structured 3-phase wizard (Brainstorm → Plan → Execute), real-time delivery tracking, and intelligent customer segmentation.

## ✨ Features

- **Chat-First Interface** — Brainstorm campaigns by describing your target and offer in plain English.
- **3-Phase Studio Wizard** — Smooth transition from *Brainstorming* (conversational segment/channel exploration) to *Plan Review* (inspect generated SQL, audience size, copy templates) to *Autonomous Execution* (real-time progress tracking).
- **AI-Powered Segmentation** — Natural language → intelligent audience filtering with AI-generated SQL (validated by `SQLGuard`).
- **Multi-Channel Delivery** — WhatsApp, SMS, Email, RCS (simulated with realistic callbacks, strictly emoji-free).
- **Real-Time Tracking** — Live delivery events streaming via SSE (sent → delivered → opened → clicked).
- **Campaign Analytics** — Delivery funnel, channel breakdown, and performance metrics updated in real-time.

## 🏗 Architecture

Detailed layout and architectural choices are documented in [architecture.md](file:///d:/AI/AIML/SUNRISE%20COUNTDOWN/ai-craftsman-portfolio/projects/XENO%20assignment/xeno-ai-crm/architecture.md).

```
┌────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Frontend  │────▶│ CRM Service  │────▶│ Channel Service  │
│  (React)   │◀────│  (FastAPI)   │◀────│   (FastAPI)      │
│  Vercel    │ SSE │  Railway     │ CB  │   Railway        │
└────────────┘     └──────┬───────┘     └──────────────────┘
                          │
                   ┌──────┴───────┐
                   │  PostgreSQL  │
                   │    Redis     │
                   └──────────────┘
```

**Three-service design:**
- **Frontend** — React + TypeScript, glassmorphism UI, SSE streaming.
- **CRM Service** — FastAPI, stateful LangGraph agent, dual LLM (Gemini + Groq model cycling fallback).
- **Channel Service** — Stub that simulates delivery and fires webhook callbacks.

## 🛠 Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React, TypeScript, Vite |
| Backend | Python, FastAPI, asyncpg |
| AI Agent | LangGraph, Gemini 2.0 Flash, Groq (Llama 3) |
| Database | PostgreSQL 16, Redis 7 |
| Deployment | Vercel (frontend), Railway (services) |

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker & Docker Compose

### 1. Clone & Setup
```bash
git clone https://github.com/omhome16/Xeno-AI--mini-CRM-agent.git
cd Xeno-AI--mini-CRM-agent

# Copy environment variables
cp .env.example .env
# Edit .env with your API keys (GEMINI_API_KEY, GROQ_API_KEY)
```

### 2. Start Infrastructure
```bash
docker-compose up -d  # PostgreSQL + Redis
```

### 3. Start CRM Service
```bash
cd crm-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 4. Start Channel Service
```bash
cd channel-service
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8001
```

### 5. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) 🎉

## 📁 Project Structure

```
xeno-ai-crm/
├── crm-service/           # CRM Backend (FastAPI)
│   ├── app/
│   │   ├── main.py        # App entry point
│   │   ├── config.py      # Environment configuration
│   │   ├── database.py    # PostgreSQL connection pools
│   │   ├── models/        # Pydantic schemas
│   │   ├── repositories/  # Data access layer
│   │   ├── services/      # Business logic
│   │   ├── agent/         # LangGraph AI agent
│   │   ├── routers/       # API endpoints
│   │   ├── workers/       # Campaign dispatch worker
│   │   └── seed/          # Demo data generation
│   ├── Dockerfile
│   └── requirements.txt
│
├── channel-service/       # Channel Stub (FastAPI)
│   ├── app/
│   │   ├── main.py        # App entry point
│   │   ├── simulator.py   # Delivery simulation
│   │   └── callback.py    # Webhook callbacks
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/              # React Frontend
│   ├── src/
│   │   ├── components/    # UI components
│   │   ├── hooks/         # Custom hooks
│   │   └── services/      # API clients
│   ├── package.json
│   └── vite.config.ts
│
├── docker-compose.yml     # Local dev infrastructure
├── .env.example           # Environment template
└── README.md
```

## 📄 License

MIT