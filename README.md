# Agentic RAG — DS & ML Knowledge Base

An intelligent question-answering system over a curated corpus of data science and machine learning books. Users ask questions through a web interface and receive cited, real-time answers powered by a dual-path agentic RAG architecture.

---

## Architecture

```
Documents (PDF · DOCX · TXT)
       │
       ▼
Loaders → Cleaners → Semantic Chunker (+ MinHash-LSH dedup)
       │
       ▼
BGE Embeddings ──► ChromaDB (dense)
BM25 Index     ──► Sparse store
       │
       ▼
User question
       │
       ▼
  QueryRouter (LLM classifier)
       │
  ┌────┴─────────────────────┐
  │                          │
  ▼                          ▼
CRAG-light graph         ReAct agent
rewrite → retrieve →     7 tools (KB search,
grade → generate         filters, compare,
(+ web fallback)         web fallback)
  │                          │
  └────────────┬─────────────┘
               ▼
    RRF fusion → MMR → CrossEncoder rerank
               │
               ▼
     Streamed answer + cited sources (SSE)
```

---

## How It Works

Each question is classified by a **LLM router** and dispatched to one of two paths:

- **CRAG-light** — rewrites the query, retrieves relevant chunks, grades their relevance, and generates an answer. Falls back to a web search if the knowledge base returns nothing useful.
- **ReAct agent** — for complex or multi-step questions, uses a set of tools to search by topic, filter by difficulty level, compare concepts, look up book metadata, or search the web.

Retrieval combines dense search (ChromaDB) and sparse search (BM25), fused via **Reciprocal Rank Fusion**, then diversified with **MMR** and reranked with a **CrossEncoder** before the final answer is generated.

---

## Tech Stack

| | |
|---|---|
| LLM | Google Gemini (configurable) |
| Embeddings | `BAAI/bge-small-en-v1.5` |
| Vector store | ChromaDB + BM25 (hybrid) |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Agent framework | LangChain + LangGraph |
| API | FastAPI + async SQLAlchemy |
| Auth | JWT + bcrypt |
| UI | React 18 + Vite + Tailwind CSS |
| Evaluation | Ragas + online LLM judge (Groq) |

---

## Features

- Hybrid retrieval with RRF fusion, MMR diversification, and CrossEncoder reranking
- Dual-path agent: CRAG-light graph and ReAct with 7 tools (category/level filters, concept comparison, web fallback)
- Real-time streaming answers via SSE
- Role-based access control (user / admin)
- Admin panel: document upload, model config hot-reload, analytics dashboard
- Per-query LLM evaluation running asynchronously in the background
- Offline Ragas evaluation pipeline

---

## Installation

**Prerequisites:** Python 3.10+, Node.js 18+

```bash
# 1. Clone and set up environment
git clone <repo-url> && cd agentic_rag
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..

# 3. Configure
cp .env.example .env  # then fill in GEMINI_API_KEY and JWT_SECRET

# 4. Initialize database
alembic upgrade head

# 5. Index your documents (place PDF/DOCX/TXT files in data/raw/ first)
python -m scripts.build_index --reset

# 6. Run
uvicorn backend.main:app --reload --port 8000  # API → http://localhost:8000
cd frontend && npm run dev                      # UI  → http://localhost:5173
```

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `JWT_SECRET` | Yes | Secret for signing JWT tokens |
| `DATABASE_URL` | No | Default: `sqlite+aiosqlite:///./data/app.db` |
| `GROQ_API_KEY` | No | Used by the online LLM judge |
| `ALLOWED_ORIGINS` | No | CORS origins, default: `http://localhost:5173` |

---

## Academic Context

> **Completed by:** Rihab Gharbi & Ghaya Ammari
> **Supervisor:** Dr. Oualid Khayati
> **Institution:** Higher Institute of Multimedia Arts of Manouba (ISAMM)
> **Specialization:** Software Engineering (INLOG) — Academic year 2025–2026
