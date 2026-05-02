# Agentic RAG — Knowledge Base Data Science / ML / IA

Système **Retrieval-Augmented Generation agentique** pour interroger en langage naturel une base de connaissances composée de livres techniques en data science, machine learning et intelligence artificielle.

L'architecture utilise un agent **LangGraph** qui orchestre dynamiquement la recherche, le filtrage et la génération : reformulation de la question → recherche vectorielle dense → évaluation de pertinence par LLM → génération de la réponse avec citations. Si aucun document pertinent n'est trouvé, l'agent reformule la question et tente une nouvelle recherche (stratégie inspirée de CRAG / Self-RAG).

---

## Table des matières

1. [Stack technique](#stack-technique)
2. [Architecture](#architecture)
3. [Prérequis matériels](#prérequis-matériels)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Utilisation](#utilisation)
7. [Structure du projet](#structure-du-projet)
8. [Détail des modules](#détail-des-modules)
9. [Fonctionnement de l'agent](#fonctionnement-de-lagent)
10. [Personnalisation](#personnalisation)
11. [Tests](#tests)
12. [Dépannage](#dépannage)
13. [Optimisations possibles](#optimisations-possibles)
14. [Roadmap](#roadmap)

---

## Stack technique

| Composant | Choix | Justification |
|---|---|---|
| **LLM** | Google Gemini 2.5 Flash | Rapide, gratuit (quota AI Studio), bonne qualité |
| **Embeddings** | `BAAI/bge-small-en-v1.5` (33 M params, 384-D) | Excellent ratio qualité/taille, tourne en CPU |
| **Vector store** | ChromaDB (mode persistant local) | Métadonnées + filtrage natifs, persistance simple |
| **Orchestration** | LangChain + LangGraph | Standard de fait pour agents RAG |
| **Document loading** | LangChain Community (PyPDF, Unstructured, BS4) | Support multi-format (PDF, MD, HTML, TXT) |
| **Chunking** | RecursiveCharacterTextSplitter | Robuste, configurable |
| **Logging** | loguru | Sortie console + fichier rotatif sans config |
| **Config** | Pydantic + YAML + dotenv | Validation forte, séparation secrets / params |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                       INDEXING PIPELINE                          │
│                                                                  │
│  data/raw/*.pdf  ──►  loaders  ──►  cleaners  ──►  chunking     │
│                                                       │          │
│                                                       ▼          │
│                                              BgeEmbedder         │
│                                                       │          │
│                                                       ▼          │
│                                              EmbeddingCache      │
│                                                       │          │
│                                                       ▼          │
│                                          ChromaDB (persisté)     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        QUERY PIPELINE                            │
│                                                                  │
│  Question utilisateur                                            │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐  ConversationMemory                             │
│  │  RagAgent   │  ◄────────────────────                          │
│  │ (LangGraph) │                                                 │
│  └─────────────┘                                                 │
│         │                                                        │
│         ▼  Graph : rewrite → retrieve → grade → generate         │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐          │
│  │  Retriever  │──► │  ChromaDB   │    │   Gemini    │          │
│  │  (MMR)      │    └─────────────┘    └─────────────┘          │
│  └─────────────┘                                                 │
│                                                                  │
│  Réponse + sources citées                                        │
└─────────────────────────────────────────────────────────────────┘
```

---



---

## Installation

### 1. Cloner / récupérer le projet

```bash
cd C:\Users\lenovo\Desktop\agentic_rag
```

### 2. Créer un environnement virtuel

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS
python -m venv .venv
source .venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

Cette étape télécharge environ **2-3 Go** (PyTorch, sentence-transformers, langchain, chromadb...) et prend 5 à 15 minutes selon votre connexion.

### 4. Configurer la clé Gemini

Récupérez une clé API gratuite sur https://aistudio.google.com/app/apikey, puis :

```bash
copy .env.example .env
```

Ouvrez `.env` et remplacez la valeur :

```
GEMINI_API_KEY=AIzaSy...votre_vraie_cle_ici...
```

**Aucun guillemet, aucun espace, aucun retour à la ligne après la clé.**

### 5. Vérifier la configuration

```bash
python -c "from src.config import get_settings; s = get_settings(); print('Key OK:', bool(s.gemini_api_key) and not s.gemini_api_key.startswith('your_'))"
```

Doit afficher `Key OK: True`.

---

## Configuration

Toute la configuration vit dans **deux fichiers** que vous pouvez modifier sans toucher au code.

### `config/config.yaml`

Hyperparamètres du système, organisés par section :

```yaml
embeddings:
  model_name: BAAI/bge-small-en-v1.5    # modèle d'embeddings
  device: cpu                            # cpu | cuda
  batch_size: 32                         # batch sentence-transformers

chunking:
  chunk_size: 800                        # caractères par chunk
  chunk_overlap: 120                     # chevauchement
  separators: ["\n\n", "\n", ". ", " ", ""]

retrieval:
  top_k: 5                               # documents à passer au LLM
  use_mmr: true                          # diversifier les résultats
  fetch_k: 20                            # candidats avant MMR

llm:
  model_name: gemini-2.5-flash           # modèle Gemini
  temperature: 0.2                       # 0=factuel, 1=créatif
  max_output_tokens: 2048

agent:
  enable_query_rewriting: true           # reformulation contextuelle
  enable_grading: true                   # filtrage des chunks non pertinents
```

### `config/prompts.yaml`

Templates de prompts utilisés par l'agent. Modifiables sans toucher au code Python — utile pour itérer sur la qualité des réponses. Quatre prompts définis : `rag_system`, `rag_user`, `reformulate_system`, `grade_system` / `grade_user`.

### `.env`

Secrets uniquement, jamais versionné :

```
GEMINI_API_KEY=...
HF_TOKEN=                # optionnel, pour les rate limits HF
LOG_LEVEL=INFO
ENV=development
```

---

## Utilisation

### Indexer la base de connaissances

Placez vos PDFs dans `data/raw/` (sous-dossiers thématiques autorisés et même recommandés — ils enrichissent les métadonnées).

**Premier index complet** (long) :

```bash
python -m scripts.build_index --reset
```

**Test rapide sur un sous-dossier** :

```bash
python -m scripts.build_index --reset --source data/raw/superficiel_grand_public --limit 500
```

**Options disponibles** :

| Option | Description |
|---|---|
| `--source PATH` | Chemin vers fichier ou dossier (défaut : `data/raw/`) |
| `--reset` | Vide la collection avant d'indexer |
| `--limit N` | Cap le nombre de chunks (utile pour tester) |

### Interroger la base

**Question unique** :

```bash
python -m scripts.query "What is overfitting in machine learning?"
```

**Mode interactif** (REPL) :

```bash
python -m scripts.query --interactive
```

Commandes spéciales en mode interactif :
- `exit` ou `quit` : sortie
- `reset` : efface l'historique de conversation

### Sortie attendue

```
======================================================================
ANSWER
======================================================================
Overfitting occurs when a model learns the training data too well,
including its noise and outliers, which results in poor generalization
to new data [source: Hands On Machine Learning - Geron.pdf]. The main
techniques to detect overfitting include cross-validation and monitoring
the gap between training and validation loss [source: Deep Learning - Goodfellow.pdf].
...
----------------------------------------------------------------------
SOURCES (5)
----------------------------------------------------------------------
1. [0.892] data\raw\fondements_ML\Hands On Machine Learning...pdf
   When training a model, the goal is to fit the data as well as...
2. [0.871] data\raw\deep_learning\Deep Learning - Ian Goodfellow...pdf
   ...
======================================================================
```

---

## Structure du projet

```
agentic_rag/
│
├── .env                          # Secrets (clé Gemini)
├── .env.example                  # Template à copier
├── .gitignore                    # Exclusions git
├── README.md                     # Ce fichier
├── requirements.txt              # Dépendances Python
├── pyproject.toml                # Config ruff / black / pytest
│
├── config/
│   ├── config.yaml               # Hyperparamètres
│   └── prompts.yaml              # Templates de prompts
│
├── data/
│   ├── raw/                      # PDFs source (organisés par thème)
│   ├── processed/                # (futur usage)
│   └── chunks/                   # (futur usage)
│
├── vector_store/
│   ├── chroma/                   # Base ChromaDB persistante
│   └── embedding_cache/          # Cache disque des embeddings
│
├── logs/
│   └── app.log                   # Logs rotatifs
│
├── src/
│   ├── config/                   # Chargement config + .env
│   ├── utils/                    # Logger, helpers IO
│   ├── ingestion/                # Loaders, cleaners, chunking
│   ├── embeddings/               # BGE embedder + cache
│   ├── vector_store/             # ChromaDB wrapper
│   ├── retrieval/                # Retriever + MMR
│   ├── llm/                      # Wrapper Gemini
│   ├── agents/                   # Agent LangGraph + mémoire + tools
│   └── pipeline/                 # Indexing + Query end-to-end
│
├── scripts/
│   ├── build_index.py            # CLI indexation
│   └── query.py                  # CLI interrogation
│
└── tests/
    ├── unit/                     # Tests unitaires
    └── integration/              # Tests d'intégration
```

---

## Détail des modules

### `src/config/`

**Rôle** : centraliser et valider toute la configuration.

`settings.py` charge `config/config.yaml` et `.env` via Pydantic. Expose deux fonctions :
- `get_settings()` : singleton `Settings` avec sous-modèles typés (`EmbeddingsConfig`, `LLMConfig`, etc.)
- `get_prompts()` : dict des templates depuis `prompts.yaml`

Avantage : si vous tapez `config.embeddings.batch_size` dans votre IDE, l'autocomplétion fonctionne ; les erreurs de typo dans le YAML lèvent une exception au démarrage, pas en runtime.

### `src/utils/`

**Rôle** : utilitaires transverses sans logique métier.

- `logger.py` : configuration loguru — sortie console colorée + fichier rotatif `logs/app.log` (10 MB, 14 jours de rétention).
- `io.py` : `text_hash()` (SHA-256 robuste aux surrogates Unicode), `ensure_dir()`, `read_jsonl()`, `write_jsonl()`.

### `src/ingestion/`

**Rôle** : transformer des fichiers bruts en chunks prêts à embedder.

- `loaders.py` : détecte automatiquement le type de fichier et utilise le loader LangChain approprié (PyPDFLoader, UnstructuredMarkdownLoader, BSHTMLLoader, TextLoader). Affiche la progression livre par livre. Supprime le bruit de pypdf.
- `cleaners.py` : nettoyage conservateur — strippe les surrogates Unicode (qui font crasher l'encodage UTF-8 sur les PDFs avec symboles mathématiques), enlève les caractères de contrôle, applique NFKC, normalise les espaces. **Pas** de lowercasing ni de suppression de ponctuation (destructeur pour le RAG).
- `chunking.py` : applique `RecursiveCharacterTextSplitter` avec les paramètres du config. Annote chaque chunk avec son `chunk_index` dans le document parent.

### `src/embeddings/`

**Rôle** : transformer du texte en vecteurs.

- `base.py` : interface abstraite `Embedder` (méthodes `embed_documents`, `embed_query`).
- `bge_embedder.py` : implémentation pour `BAAI/bge-small-en-v1.5`. Charge le modèle via sentence-transformers, applique le préfixe BAAI sur les requêtes (`"Represent this sentence for searching relevant passages: "`), normalise les vecteurs.
- `cache.py` : cache disque persistant. Chaque texte est haché (SHA-256) et stocké dans `vector_store/embedding_cache/XX/<hash>.npy` (sharding par 2 caractères pour éviter des dossiers à 100K fichiers). Permet de relancer l'indexation sans recalculer ce qui n'a pas changé — économise des heures.

### `src/vector_store/`

**Rôle** : indexer et rechercher les vecteurs.

- `base.py` : interface `VectorStore` + dataclass `SearchResult` (id, text, score, metadata).
- `chroma_store.py` : wrapper ChromaDB persistant. Convertit les distances Chroma (où plus petit = plus proche) en scores de similarité (où plus grand = plus pertinent).

### `src/retrieval/`

**Rôle** : fusionner embedder + vector store en une interface de recherche.

- `retriever.py` : embed la requête → search ChromaDB → applique MMR si activé. Le **MMR** récupère 20 candidats puis sélectionne le top_k en pénalisant ceux trop similaires entre eux — évite que les 5 chunks retournés soient 5 paraphrases du même paragraphe.

### `src/llm/`

**Rôle** : abstraire l'appel au LLM.

- `base.py` : interface `LLM`.
- `gemini_client.py` : wrapper sur `ChatGoogleGenerativeAI`. Expose `generate(prompt, system)` simple, `chat(messages)` multi-tour, et `as_langchain()` pour intégration LangGraph.

### `src/agents/`

**Rôle** : orchestrer l'agent agentique.

- `memory.py` : mémoire conversationnelle sliding-window (10 derniers tours).
- `tools.py` : factory de `knowledge_base_search` — outil LangChain qui wrappe le retriever, utilisable par un agent LangGraph en mode tool-calling.
- `base_agent.py` : interface `BaseAgent` (méthode `run(question) -> dict`).
- `rag_agent.py` : **cœur du système agentique**. Définit un graphe LangGraph avec quatre nœuds connectés conditionnellement (voir section [Fonctionnement de l'agent](#fonctionnement-de-lagent)).

### `src/pipeline/`

**Rôle** : orchestrations end-to-end appelables d'une seule ligne.

- `indexing_pipeline.py` : load → clean → chunk → embed → upsert ChromaDB. Traitement par batches de 256 chunks avec barre de progression `tqdm`. Tolérant aux pannes : si un batch échoue, le suivant continue.
- `query_pipeline.py` : instancie tous les composants (embedder, store, retriever, llm, memory, agent) et expose une API simple `pipeline.ask(question)`.

### `scripts/`

CLI minimalistes qui consomment les pipelines.

- `build_index.py` : argparse → `IndexingPipeline.run()`.
- `query.py` : argparse + REPL → `QueryPipeline.ask()` + affichage formaté de la réponse et des sources.

### `tests/`

- `unit/` : tests rapides sans dépendance réseau (settings, cleaning, chunking, cache).
- `integration/` : test bout-en-bout, désactivé par défaut (`pytest.mark.skipif`), activable via `RUN_INTEGRATION=1 pytest`.

---

## Fonctionnement de l'agent

L'agent est un **graphe d'états LangGraph** :

```
                    ┌──────────┐
        START ────► │ rewrite  │
                    └────┬─────┘
                         │
                         ▼
                    ┌──────────┐
                    │ retrieve │
                    └────┬─────┘
                         │
                         ▼
                    ┌──────────┐
                    │  grade   │
                    └────┬─────┘
                         │
              ┌──────────┴──────────┐
        relevant ≥ 1            relevant = 0
              │                      │
              ▼                      ▼
        ┌──────────┐         ┌────────────┐
        │ generate │         │  rewrite   │  (max 1 retry)
        └────┬─────┘         └─────┬──────┘
             │                     │
             ▼                     ▼
            END                retrieve...
```

### Détail des nodes

**`rewrite`** : si l'historique contient au moins une réponse précédente de l'assistant, reformule la question utilisateur en une requête standalone (ex: "et comment l'éviter ?" devient "Comment éviter l'overfitting en ML ?"). Au premier tour, est skippé.

**`retrieve`** : embed la question reformulée, recherche les `fetch_k=20` candidats dans Chroma, applique MMR pour garder les `top_k=5` les plus pertinents et diversifiés.

**`grade`** : pour chaque chunk retourné, demande à Gemini "ce passage est-il pertinent pour répondre à la question ?". Filtre les chunks non pertinents. Si le retriever a ramené 5 chunks dont 3 sont "yes" et 2 "no", on continue avec 3 chunks.

**Routage conditionnel** : si après filtrage il reste au moins 1 chunk pertinent → `generate`. Si 0 chunks pertinents et c'est le 1er essai → retour à `rewrite` pour tenter une autre formulation. Si 0 chunks et déjà retry → `generate` avec un message "contexte insuffisant".

**`generate`** : construit le prompt final avec les chunks comme contexte + question, appelle Gemini, retourne la réponse avec citations `[source: <doc>]`.

### Inspiration

Cette architecture s'inspire de **CRAG** (Corrective RAG, Yan et al. 2024) et **Self-RAG** (Asai et al. 2023) en version simplifiée. Le grader ajoute une étape de réflexion entre retrieval brut et génération, ce qui réduit les hallucinations dues à des chunks faiblement pertinents.

---

## Personnalisation

### Changer le modèle d'embeddings

Dans `config/config.yaml` :

```yaml
embeddings:
  model_name: intfloat/multilingual-e5-small    # multilingue
  query_prefix: "query: "                        # préfixe E5
  passage_prefix: "passage: "
```

Puis ré-indexez avec `--reset`. Le cache d'embeddings est invalidé car les vecteurs n'ont pas la même origine.

### Changer la taille des chunks

```yaml
chunking:
  chunk_size: 1200      # plus gros = moins de chunks, plus de contexte par chunk
  chunk_overlap: 200
```

Ré-indexez avec `--reset`.

### Désactiver le grading (plus rapide, moins précis)

```yaml
agent:
  enable_grading: false
```

Skip l'appel Gemini de filtrage. Économise ~1 appel LLM par chunk retrieved (5 appels/question par défaut).

### Ajouter un filtre par métadonnées

Dans le code (par exemple `query_pipeline.py`), passez `where` au retriever :

```python
results = self.retriever.retrieve(
    question,
    where={"source": {"$contains": "deep_learning"}}
)
```

Ne fouille que dans les PDFs du dossier `deep_learning/`.

---

## Tests

```bash
# Tous les tests unitaires (rapide)
pytest

# Avec couverture
pytest --cov=src --cov-report=html

# Tests d'intégration (lent, requiert Gemini API + modèle téléchargé)
$env:RUN_INTEGRATION="1"      # PowerShell
pytest tests/integration
```

---

## Dépannage

### `API key not valid`

Votre `.env` n'a pas une clé Gemini valide. Régénérez-la sur https://aistudio.google.com/app/apikey, vérifiez `type .env` qu'il n'y a ni guillemets ni espaces parasites.

### `cannot import name 'X' from 'Y'`

Vous avez probablement un fichier `__init__.py` mal synchronisé. Vérifiez que les exports correspondent aux noms réels.

### `UnicodeEncodeError: 'utf-8' codec can't encode character '\ud8XX'`

Surrogate Unicode dans un PDF mal extrait. Le cleaner les strippe normalement — assurez-vous que `clean=True` est passé à `chunk_documents`.

### Indexation extrêmement lente (> 1 jour)

Quelques chunks peuvent être pathologiques (extraction PDF ratée → blob de 50 000 caractères). Ajoutez un filtre dans `indexing_pipeline.py` :

```python
chunks = [c for c in chunks if 100 <= len(c.page_content) <= 4000]
```

### `gemini-2.5-flash` indisponible

Repassez à `gemini-1.5-flash` dans `config/config.yaml` — toujours supporté et largement suffisant pour ce cas d'usage.

### `chromadb` plante après mise à jour

Supprimez `vector_store/chroma/` et ré-indexez. Le format de sérialisation Chroma a changé entre certaines versions.

---

## Optimisations possibles

### Vitesse d'indexation

- **ONNX + INT8** : convertir bge-small en ONNX quantifié donne **2-4× de speedup** CPU sans perte de qualité.

  ```bash
  pip install optimum[onnxruntime]
  optimum-cli export onnx --model BAAI/bge-small-en-v1.5 bge-onnx/
  optimum-cli onnxruntime quantize --avx512_vnni --onnx_model bge-onnx/ -o bge-int8/
  ```

- **Parallélisation** : actuellement séquentiel. Avec `concurrent.futures.ProcessPoolExecutor` sur les batches, gain x2-3 sur multi-cœur.

### Qualité du retrieval

- **Cross-encoder reranker** : ajouter `BAAI/bge-reranker-base` après le retriever pour re-scorer les top-20 candidats avant grading. Boost typique de +5-10 % sur les benchmarks RAG.

- **Hybrid search** : combiner dense (BGE) + sparse (BM25) avec fusion RRF. Particulièrement utile pour les requêtes contenant des termes techniques rares.

- **Query expansion** : générer 3-5 variations de la question avec Gemini, fusionner les résultats. Améliore le recall.

### Robustesse

- **Filtre anti-chunks pathologiques** : rejeter les chunks de plus de 4000 caractères ou de moins de 100 caractères avant embedding.

- **Détection des doublons** : nombre de PDFs sont des éditions différentes du même livre. Un near-duplicate detector évite les chunks redondants.

---

## Roadmap

### Court terme

- [ ] Cap des chunks (100 ≤ len ≤ 4000) pour éviter les blocages d'indexation
- [ ] Reranker cross-encoder optionnel
- [ ] Conversion ONNX automatique de l'embedder

### Moyen terme

- [ ] Outil web search (Tavily / DuckDuckGo) en fallback quand le KB ne suffit pas
- [ ] UI Streamlit avec affichage des sources et de la trace de l'agent
- [ ] Endpoint FastAPI pour exposer le système en API REST
- [ ] Évaluation automatisée (Ragas : faithfulness, answer relevancy, context precision)

### Long terme

- [ ] Multi-modalité : extraire et embedder les figures / équations des PDFs
- [ ] Re-indexation incrémentale (détection des fichiers ajoutés / modifiés)
- [ ] Mémoire long-terme persistée (Redis / SQLite) pour conversations multi-sessions

---

## Crédits

- **BAAI** pour le modèle d'embeddings `bge-small-en-v1.5`
- **Google** pour Gemini et l'API gratuite via AI Studio
- **Chroma** pour la base vectorielle
- **LangChain / LangGraph** pour l'orchestration

---

## Licence

Projet personnel — usage libre. Les livres dans `data/raw/` ne sont **pas** redistribués avec ce projet ; assurez-vous de respecter leurs licences respectives.
