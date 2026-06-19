# PathFinder AI — AI Life Decision Simulator

An AI-powered tool that helps you simulate major life decisions — career changes, education paths, relocation, and more — by combining web research, financial projections, Monte Carlo simulation, and tradeoff analysis into a ranked set of scenarios.

---

## How It Works

1. **Intake** — Fill in a short form (name, current situation, decision domain, location, and the options you're already considering). The AI then holds a short conversation to fill in missing context — your values, hard constraints, soft preferences, risk tolerance, and time horizon.
2. **Scenario Generation** — The AI generates 6–8 realistic decision paths tailored to your profile.
3. **Research** — For each scenario, 6 targeted web searches are run (qualitative + quantitative). Results are embedded and stored in Qdrant, then the most relevant chunks are retrieved to keep token usage low.
4. **Monte Carlo Simulation** — 5,000 income simulations per scenario produce probability distributions and a risk label (low / medium / high).
5. **Tradeoff Analysis** — Each scenario is scored across dimensions (financial, lifestyle, risk, time).
6. **Ranked Results** — Scenarios are ranked by a composite score and displayed with research bullets, salary percentiles, 5-year projections, and tradeoff breakdowns.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| Backend | FastAPI (Python 3.11+) |
| LLM | OpenAI API (`gpt-4o-mini`) |
| Web Search | Tavily API |
| Vector DB | Qdrant (Docker) |
| Embeddings | `all-MiniLM-L6-v2` via sentence-transformers (384-dim) |
| Simulation | Monte Carlo (Python stdlib `random`, runs in-process) |
| Session Storage | JSON files (`backend/sessions/`) |

---

## Prerequisites

- Docker
- Python 3.11+
- Node.js 18+
- An [OpenAI API key](https://platform.openai.com/api-keys)
- A [Tavily API key](https://app.tavily.com) (free tier)

---

## Setup

### 1. Clone the repo

```bash
git clone <repo-url>
cd life-decision-simulator
```

### 2. Backend environment

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create `backend/.env`:

```env
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-your_openai_key_here
TAVILY_API_KEY=tvly-your_tavily_key_here
```

> Do not wrap values in quotes.

### 3. Frontend dependencies

```bash
cd frontend
npm install
```

---

## Running

You need **3 terminals** open simultaneously.

**Terminal 1 — Qdrant (vector database)**
```bash
docker run -p 6333:6333 qdrant/qdrant
```

**Terminal 2 — Backend**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The `all-MiniLM-L6-v2` embedding model (~90 MB) is loaded lazily — on the first analysis that needs it, not at startup — and then cached in `~/.cache/huggingface/`. So the first analysis run takes a little longer while the model downloads.

Wait for:
```
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

**Terminal 3 — Frontend**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Testing

The backend ships with a pytest suite that runs without any API keys, Qdrant, or network access (the retriever and web search degrade gracefully when unavailable).

```bash
cd backend
source .venv/bin/activate
pytest
```

- `tests/test_smoke.py` — API health, session lifecycle, and endpoint guardrails (prerequisite checks return HTTP 400).
- `tests/test_simulation.py` — Monte Carlo engine invariants (percentile ordering, probability bounds, risk labels, debt/idle effects).

These same tests run automatically in CI on every push and pull request — see [.github/workflows/ci.yml](.github/workflows/ci.yml).

---

## Project Structure

```
life-decision-simulator/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── base.py              # Abstract BaseAgent + AgentOutput
│   │   │   ├── intake.py            # Multi-turn profile-building conversation
│   │   │   ├── scenario_generator.py
│   │   │   ├── research.py          # Web search + Qdrant RAG + synthesis
│   │   │   ├── market_outlook.py
│   │   │   ├── tradeoff_analyzer.py
│   │   │   ├── what_if.py
│   │   │   └── orchestrator.py
│   │   ├── tools/
│   │   │   ├── retriever.py         # Qdrant vector store (Docker client)
│   │   │   ├── web_search.py        # Tavily search wrapper
│   │   │   └── progress.py          # SSE progress queue
│   │   ├── simulation/
│   │   │   ├── __init__.py          # exposes simulate_all
│   │   │   └── monte_carlo.py       # Monte Carlo engine (Python random)
│   │   ├── main.py                  # FastAPI routes + SSE stream endpoint
│   │   ├── state.py                 # FileStore session persistence
│   │   ├── schemas.py
│   │   ├── llm.py                   # OpenAI client + JSON-validate/retry
│   │   └── config.py
│   ├── tests/                       # pytest suite (smoke + simulation)
│   ├── sessions/                    # Auto-created; JSON session files
│   ├── pyproject.toml
│   ├── .env.example
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Phase machine + session resume logic
│   │   ├── api.ts                   # Typed fetch wrappers for the backend
│   │   ├── types.ts                 # Shared TS types mirroring backend schemas
│   │   ├── main.tsx                 # React entry point
│   │   ├── components/
│   │   │   ├── IntakeForm.tsx
│   │   │   ├── ChatView.tsx         # Intake chat with profile-complete buttons
│   │   │   ├── ChatPanel.tsx        # Free-form follow-up chat
│   │   │   ├── ScenarioCards.tsx    # Ranked scenario cards
│   │   │   ├── TradeoffMatrix.tsx   # Scenario × dimension scoring grid
│   │   │   ├── DecisionBrief.tsx    # Final synthesized recommendation
│   │   │   └── WhatIfBox.tsx        # What-if perturbation input
│   │   └── styles.css
│   └── vite.config.ts
├── .github/
│   └── workflows/
│       └── ci.yml                   # CI: backend pytest + frontend build
└── README.md
```

---

## Key Design Decisions

**Token reduction via RAG** — Each scenario runs 6 web queries (8 results each = ~3,200 tokens of raw text). Qdrant stores these as embeddings and retrieves only the top 6 most relevant chunks (~600 tokens), saving ~2,600 tokens per synthesis call.

**Session persistence** — Sessions are saved as JSON files in `backend/sessions/` and session ID + chat history are stored in `localStorage`. Refreshing the page or restarting the backend resumes from where you left off.

**Live progress via SSE** — The frontend opens a Server-Sent Events stream before calling `/api/analysis/run`. Each agent step emits a message to the stream so the user sees real-time progress during the 2–4 minute analysis.

---

## Environment Variables

| Variable | Description |
|---|---|
| `LLM_BASE_URL` | OpenAI-compatible endpoint (default: OpenAI) |
| `LLM_MODEL` | Model name (default: `gpt-4o-mini`) |
| `LLM_API_KEY` | API key for the LLM provider |
| `TAVILY_API_KEY` | Tavily web search API key |
