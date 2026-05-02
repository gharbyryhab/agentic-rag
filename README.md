# Agentic RAG — Data Science / ML / AI Knowledge Base

Système RAG agentique pour interroger une base de connaissances en data science, machine learning et intelligence artificielle.

## Stack

- **LLM** : Google Gemini (`gemini-1.5-flash`)
- **Embeddings** : `BAAI/bge-small-en-v1.5` (local, CPU)
- **Vector store** : ChromaDB (persistant local)
- **Orchestration** : LangChain + LangGraph

## Installation

```bash
# 1. Créer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # Linux/Mac

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer la clé Gemini
copy .env.example .env
# puis ouvrir .env et coller votre clé GEMINI_API_KEY
```

## Utilisation

```bash
# Construire l'index à partir de data/raw
python -m scripts.build_index

# Poser une question en CLI
python -m scripts.query "What is the difference between LoRA and full fine-tuning?"
```

## Structure

```
src/
  config/        # Chargement config + .env
  ingestion/     # Loaders + chunking
  embeddings/    # BGE + cache
  vector_store/  # ChromaDB
  retrieval/     # Recherche dense + MMR
  llm/           # Wrapper Gemini
  agents/        # Graphe LangGraph (retrieve → grade → generate)
  pipeline/      # Indexing + Query end-to-end
  utils/         # Logger, IO
```

## Tests

```bash
pytest
```
