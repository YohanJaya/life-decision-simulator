# Second Brain — AI Life Decision Simulator

An AI-powered tool that helps you simulate major life decisions — career changes, education paths, relocation, and more — by combining web research, financial projections, Monte Carlo simulation, and tradeoff analysis into a ranked set of scenarios.

---

## How It Works

1. **Intake** — Fill in a short form (age, income, goal, time horizon). The AI then holds a short conversation to fill in missing context.
2. **Scenario Generation** — The AI generates 3–5 realistic decision paths tailored to your profile.
3. **Research** — For each scenario, 6 targeted web searches are run (qualitative + quantitative). Results are embedded and stored in Qdrant, then the most relevant chunks are retrieved to keep token usage low.
4. **Monte Carlo Simulation** — 1,000 income simulations per scenario produce probability distributions and a risk label (low / medium / high).
5. **Tradeoff Analysis** — Each scenario is scored across dimensions (financial, lifestyle, risk, time).
6. **Ranked Results** — Scenarios are ranked by a composite score and displayed with research bullets, salary percentiles, 5-year projections, and tradeoff breakdowns.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| Backend | FastAPI (Python 3.11+) |
| LLM | Groq API (`llama-3.1-8b-instant`) |
| Web Search | Tavily API |
| Vector DB | Qdrant (Docker) |
| Embeddings | `all-MiniLM-L6-v2` via sentence-transformers (384-dim) |
| Simulation | NumPy Monte Carlo (runs in-process) |
| Session Storage | JSON files (`backend/sessions/`) |

---

## Prerequisites

- Docker
- Python 3.11+
- Node.js 18+
- A [Groq API key](https://console.groq.com) (free tier)
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
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.1-8b-instant
LLM_API_KEY=gsk_your_groq_key_here
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

On first run, the `all-MiniLM-L6-v2` embedding model (~90 MB) downloads automatically and is cached in `~/.cache/huggingface/`.

Wait for:
```
INFO Qdrant client connected to localhost:6333
INFO Sentence-transformer model loaded (dim=384)
INFO:     Application startup complete.
```

**Terminal 3 — Frontend**
```bash
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Project Structure

```
life-decision-simulator/
├── backend/
│   ├── app/
│   │   ├── agents/
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
│   │   ├── main.py                  # FastAPI routes + SSE stream endpoint
│   │   ├── state.py                 # FileStore session persistence
│   │   ├── simulation.py            # Monte Carlo engine
│   │   ├── schemas.py
│   │   ├── llm.py                   # Groq client + rate-limit semaphore
│   │   └── config.py
│   ├── sessions/                    # Auto-created; JSON session files
│   ├── pyproject.toml
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── App.tsx                  # Phase machine + session resume logic
│   │   ├── api.ts
│   │   ├── components/
│   │   │   ├── IntakeForm.tsx
│   │   │   ├── ChatView.tsx         # Intake chat with profile-complete buttons
│   │   │   └── ScenarioCards.tsx
│   │   └── styles.css
│   └── vite.config.ts
└── README.md
```

---

## Key Design Decisions

**Rate limit management** — Groq's free tier allows ~6,000 tokens/min. A `asyncio.Semaphore(1)` + 10-second sleep between LLM calls serializes requests and stays safely under the limit.

**Token reduction via RAG** — Each scenario runs 6 web queries (8 results each = ~3,200 tokens of raw text). Qdrant stores these as embeddings and retrieves only the top 6 most relevant chunks (~600 tokens), saving ~2,600 tokens per synthesis call.

**Session persistence** — Sessions are saved as JSON files in `backend/sessions/` and session ID + chat history are stored in `localStorage`. Refreshing the page or restarting the backend resumes from where you left off.

**Live progress via SSE** — The frontend opens a Server-Sent Events stream before calling `/api/analysis/run`. Each agent step emits a message to the stream so the user sees real-time progress during the 2–4 minute analysis.

---

## Environment Variables

| Variable | Description |
|---|---|
| `LLM_BASE_URL` | OpenAI-compatible endpoint (default: Groq) |
| `LLM_MODEL` | Model name (default: `llama-3.1-8b-instant`) |
| `LLM_API_KEY` | API key for the LLM provider |
| `TAVILY_API_KEY` | Tavily web search API key |
