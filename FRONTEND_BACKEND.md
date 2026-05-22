# Lancer le Frontend & Backend

## Prérequis
- Venv RAG activé (`source ~/agentic-rag-venv/bin/activate`)
- Node.js ≥ 18 installé

---

## 1. Backend (FastAPI)

```bash
# Depuis la racine du projet, venv activé
pip install -r backend/requirements.txt

uvicorn backend.main:app --reload --port 8000
```

→ API disponible sur http://localhost:8000  
→ Swagger UI : http://localhost:8000/docs

---

## 2. Frontend (React + Vite)

```bash
cd frontend
npm install
npm run dev
```

→ Interface disponible sur http://localhost:5173

---

## 3. Importer un run Ragas dans le dashboard

Après avoir lancé une évaluation :
```bash
python -m tools.eval.run_ragas --tag mon_tag
```

Dans le Dashboard → section "Import Ragas run" → entrer `mon_tag` → cliquer **Import**.

---

## Structure

```
agentic-rag/
├── backend/
│   ├── main.py          # FastAPI app
│   ├── database.py      # SQLite + SQLAlchemy async
│   ├── models.py        # ORM models (Session, Message, Feedback, EvalRun…)
│   ├── schemas.py       # Pydantic schemas
│   ├── requirements.txt
│   └── routers/
│       ├── chat.py      # POST /chat
│       ├── sessions.py  # GET/DELETE /sessions
│       ├── feedback.py  # POST /messages/{id}/feedback
│       └── metrics.py   # GET /metrics/dashboard|eval|logs
└── frontend/
    ├── src/
    │   ├── pages/
    │   │   ├── Chat.jsx       # Interface de chat
    │   │   ├── Dashboard.jsx  # Métriques & Ragas
    │   │   └── History.jsx    # Historique des sessions
    │   └── api.js             # Appels API centralisés
    └── package.json
```

## Base de données

SQLite créée automatiquement dans `data/app.db` au premier démarrage du backend.

Tables : `sessions`, `messages`, `feedback`, `request_logs`, `eval_runs`, `eval_metrics`
