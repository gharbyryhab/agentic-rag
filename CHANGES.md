# Changelog — Agentic RAG

Suivi quotidien des modifications apportées au projet.

---

## 21 Mai 2025 — Branch `fix/online-eval-web-search`

### 1. Évaluation en ligne (Online Judge) — `src/eval/online_judge.py`

**Problème :** Le juge d'évaluation utilisait un scoring entier (0–5) produit par le modèle RAG lui-même, introduisant un biais d'auto-évaluation. De plus, le résultat s'affichait à l'intérieur du prompt `You>` au lieu d'apparaître après les sources, et le champ `reason` n'était pas sauvegardé dans le fichier de log.

**Corrections apportées :**

- **Nouveau provider indépendant (Groq)** : le juge utilise désormais `llama-3.3-70b-versatile` via l'API Groq, séparé du modèle RAG (Gemma), pour éviter l'auto-évaluation. Configurable dans `config/config.yaml` sous `online_eval.judge`.

- **Nouvelles métriques standard RAG** : remplacement du score 0–5 par deux métriques reconnues :
  - `faithfulness` (0.0–1.0) : chaque affirmation de la réponse est-elle ancrée dans le contexte récupéré ?
  - `answer_relevancy` (0.0–1.0) : la réponse adresse-t-elle directement la question posée ?

- **Champ `reason` sauvegardé** : le juge extrait et persiste une phrase d'explication dans chaque entrée de `results/logs/runtime_quality.jsonl`.

- **Affichage corrigé** : `maybe_evaluate()` retourne désormais un `Future`. `QueryPipeline` expose `flush_judge()` qui bloque jusqu'à la fin de l'évaluation en arrière-plan. Le mode interactif (`scripts/query.py`) appelle `flush_judge()` après l'affichage des sources — le résumé `[OnlineJudge]` s'affiche donc toujours avant le prochain `You>`.

**Fichiers modifiés :**
- `src/eval/online_judge.py`
- `src/pipeline/query_pipeline.py`
- `config/config.yaml` (section `online_eval.judge`)
- `config/prompts.yaml` (prompts `judge_online_system` / `judge_online_user`)
- `src/config/settings.py` (nouveau `OnlineJudgeConfig`)

---

### 2. Agent ReAct — timeout natif LangGraph — `src/agents/react_agent.py`

**Problème :** Le timeout était géré manuellement via un thread daemon (`threading.Thread`). En cas de dépassement, le thread restait en vie en arrière-plan et l'état du graphe était transmis via un dictionnaire partagé non thread-safe.

**Correction :** Suppression du module `threading`. Le timeout est maintenant passé directement à LangGraph via `config={"timeout": timeout_s}` dans `graph.stream()`. LangGraph lève une `TimeoutError` native, interceptée proprement et relayée vers le fallback de `RagAgent`.

**Fichiers modifiés :**
- `src/agents/react_agent.py`

---

### 3. Détection des modèles Gemma — `src/llm/gemini_client.py`

**Problème :** `_is_gemma3()` cherchait la chaîne `"gemma-3"` dans le nom du modèle. Avec le modèle actuel `gemma-4-26b-a4b-it`, la condition était fausse → tous les `SystemMessage` étaient transmis directement au modèle, qui ne les supporte pas, provoquant des erreurs silencieuses ou des comportements inattendus (prompts du grader, du router, du générateur ignorés).

**Correction :** La vérification porte désormais sur `"gemma"` (insensible à la casse), couvrant toutes les versions Gemma présentes et futures.

```python
# Avant
return "gemma-3" in self._cfg.model_name

# Après
return "gemma" in self._cfg.model_name.lower()
```

**Fichiers modifiés :**
- `src/llm/gemini_client.py`

---

### 4. Recherche web — URL dans les sources — `src/agents/tools.py` / `src/agents/rag_agent.py`

**Problème :** Les résultats de recherche web (DuckDuckGo) n'incluaient pas l'URL source. L'utilisateur ne pouvait pas vérifier l'origine des informations retournées par le web fallback.

**Corrections apportées :**

- **Chemin agent (ReAct)** : `search_web` inclut désormais `h['href']` dans le texte formaté retourné à l'agent, visible dans les snippets des sources.

- **Chemin simple (CRAG-light)** : `_node_web_fallback` construit une liste `web_sources` avec un champ `url` explicite. `_run_simple` ajoute ces sources à la liste retournée.

- **Affichage** : `_print_result` dans `scripts/query.py` affiche la ligne URL sous chaque source web.

**Fichiers modifiés :**
- `src/agents/tools.py`
- `src/agents/rag_agent.py`
- `scripts/query.py`

---

### Résumé des fichiers modifiés

| Fichier | Type de modification |
|---|---|
| `src/eval/online_judge.py` | Refactor + fix |
| `src/pipeline/query_pipeline.py` | Fix |
| `src/agents/react_agent.py` | Fix |
| `src/agents/tools.py` | Fix |
| `src/agents/rag_agent.py` | Fix |
| `src/llm/gemini_client.py` | Bug fix |
| `src/config/settings.py` | Ajout `OnlineJudgeConfig` |
| `config/config.yaml` | Ajout section `online_eval.judge` |
| `config/prompts.yaml` | Réécriture prompts juge |
| `scripts/query.py` | Fix affichage |

---

## 22 Mai 2026 — Corrections agent + métriques Ragas

### 1. Snippets non tronqués — `src/agents/rag_agent.py` / `src/agents/react_agent.py`

**Problème :** Les sources retournées au pipeline d'évaluation Ragas contenaient des snippets tronqués à 200 ou 300 caractères. Le judge LLM de Ragas comparait les claims de la réponse à ces contextes amputés → des claims légitimes semblaient non supportés → `faithfulness` artificiellement basse.

**Corrections apportées :**

- `rag_agent.py` — path simple, sources KB : `d.text[:200]` → `d.text`
- `rag_agent.py` — path web fallback : `h.get("body", "")[:300]` → `h.get("body", "")`
- `react_agent.py` — path ReAct, tool outputs : `tool_text[:300]` → `tool_text`

**Fichiers modifiés :**
- `src/agents/rag_agent.py`
- `src/agents/react_agent.py`

---

### 2. Détection OOD avant routing — `src/agents/rag_agent.py` / `config/prompts.yaml`

**Problème :** Le router ne connaissait que deux sorties (`simple` / `agent`). Une question hors domaine ("prix de l'or ?") déclenchait le pipeline complet — 7 appels LLM, ~90 secondes — pour conclure qu'il n'y a rien dans la KB.

**Correction :** Ajout d'un appel LLM minimal **avant** le router avec un prompt `ood_check_system` qui attend un seul mot : `yes` (dans le domaine) ou `no` (hors domaine). Si `no` → réponse polie immédiate, route `"out_of_domain"`, zéro appel LLM supplémentaire. En cas d'erreur LLM → fail-safe `False` (on laisse toujours passer).

Les cas limites ("ML en finance", "IA en médecine") sont définis comme `yes` dans le prompt pour éviter les faux positifs.

```
Avant : memory check → router → pipeline complet (7 LLM)
Après : memory check → OOD check (1 LLM) → router → pipeline
                            │ "no"
                            └─► réponse immédiate, 0 LLM de plus
```

**Fichiers modifiés :**
- `src/agents/rag_agent.py` — nouvelle méthode `_check_out_of_domain()`
- `config/prompts.yaml` — ajout du prompt `ood_check_system`

---

### 3. Rewrite partagé entre path simple et ReAct — `src/agents/rag_agent.py`

**Problème :** Le path `simple` reformulait la question avec l'historique de conversation avant de chercher (`_node_rewrite`). Le path `agent` (ReAct) envoyait la question brute directement. Une question de suivi comme "explique le premier" arrivait à ReAct sans contexte → appels d'outils sur "le premier" → 0 résultat pertinent.

**Correction :** Extraction de la logique de reformulation dans une méthode partagée `_rewrite_question(question, history) → str`, appelée par les deux paths. `_node_rewrite` est simplifié pour déléguer à ce helper. Dans `run()`, la question reformulée remplace la question brute avant d'entrer dans ReAct.

```
Avant :
  simple → rewrite (reformule) → retrieve
  agent  → ReAct (question brute "explique le premier")

Après :
  simple → _node_rewrite (via helper) → retrieve
  agent  → _rewrite_question() → ReAct (question autonome reformulée)
```

**Fichiers modifiés :**
- `src/agents/rag_agent.py` — ajout `_rewrite_question()`, simplification `_node_rewrite`, appel rewrite avant ReAct dans `run()`

---

### Résumé des fichiers modifiés

| Fichier | Type de modification |
|---|---|
| `src/agents/rag_agent.py` | Fix snippets + ajout OOD check + rewrite partagé |
| `src/agents/react_agent.py` | Fix snippets tronqués |
| `config/prompts.yaml` | Ajout prompt `ood_check_system` |



---

## 9. Corrections agent — Session 21 mai 2026

> **Objectif** : corriger les bugs critiques du pipeline RAG identifiés après analyse des mauvaises métriques Ragas, et améliorer le comportement de l'agent sur les questions hors domaine et les conversations multi-tours.

---

### 9.1 Bugs corrigés

| # | Bug | Fichier | Symptôme | Fix |
|---|-----|---------|----------|-----|
| 1 | `_is_gemma3()` ne détecte pas Gemma-4 | `src/llm/gemini_client.py` | `SystemMessage` envoyé à Gemma-4 → rejeté silencieusement → prompts ignorés → faithfulness catastrophique | `"gemma-3" in model_name` → `"gemma" in model_name.lower()` |
| 2 | Snippets tronqués à 200 chars (sources KB) | `src/agents/rag_agent.py` | Ragas ne voit que le début de chaque chunk → claims non vérifiables → faithfulness artificiellement basse | `d.text[:200]` → `d.text` |
| 3 | Snippets tronqués à 300 chars (web fallback) | `src/agents/rag_agent.py` | Même problème que #2 sur le path web | `h.get("body","")[:300]` → `h.get("body","")` |
| 4 | Snippets tronqués à 300 chars (path ReAct) | `src/agents/react_agent.py` | Même problème que #2 sur le path agent | `tool_text[:300]` → `tool_text` |
| 5 | UPDATE cartesian product SQLAlchemy | `backend/routers/chat.py` | `SAWarning: cartesian product` à chaque message | `updated_at=Message.created_at` → `updated_at=datetime.utcnow()` |

---

### 9.2 Amélioration — OOD check avant routing

**Problème :** toute question — même complètement hors domaine ("prix de l'or ?") — passait par le pipeline complet : 7 appels LLM, ~90 secondes, pour conclure qu'il n'y a rien dans la KB.

**Solution :** ajout d'un appel LLM minimal **avant** le router, avec un prompt `ood_check_system` qui demande un seul mot (`yes` / `no`).

```
Avant :   memory check → router → pipeline complet (~7 LLM)
Après :   memory check → OOD check (1 LLM) → router → pipeline
                              │
                         "no" = hors domaine
                              │
                         réponse polie immédiate
                         0 appel LLM supplémentaire
```

**Fichiers modifiés :**
- `config/prompts.yaml` — ajout du prompt `ood_check_system`
- `src/agents/rag_agent.py` — ajout de la méthode `_check_out_of_domain(question) → bool`

**Comportement :**
- Question hors domaine → `no` → réponse immédiate, route `"out_of_domain"`
- Cas limite ("ML en finance") → `yes` → pipeline normal
- Erreur LLM OOD → fail-safe : `False` → pipeline normal (jamais bloquant)

---

### 9.3 Amélioration — Rewrite partagé entre path simple et path ReAct

**Problème :** le path `simple` reformulait la question avec l'historique de conversation (`_node_rewrite`), mais le path `agent` (ReAct) envoyait la question brute directement. Une question comme "explique le premier" arrivait à ReAct sans contexte → recherche KB sur "le premier" → 0 résultat.

**Solution :** extraction de la logique de reformulation dans une méthode partagée `_rewrite_question()`, appelée par les deux paths.

```
Avant :
  simple → _node_rewrite (reformule) → retrieve
  agent  → ReAct (question brute "explique le premier")

Après :
  simple → _node_rewrite (appelle _rewrite_question) → retrieve
  agent  → _rewrite_question → ReAct (question reformulée autonome)
```

**Fichier modifié :** `src/agents/rag_agent.py`

- Nouvelle méthode `_rewrite_question(question, history) → str`
  - Retourne la question originale si c'est le premier tour (pas d'historique assistant)
  - Appelle le LLM de reformulation si historique présent
  - Fail-safe : retourne la question originale en cas d'erreur
- `_node_rewrite` simplifié : délègue à `_rewrite_question()` (plus de duplication)
- `run()` : avant d'appeler `react_agent.run()`, applique `_rewrite_question()` en priorité

---

### 9.4 Pipeline agent final après corrections

```
Question de l'utilisateur
         │
         ▼
  Memory check ──────────────────────────────► réponse mémoire (si applicable)
         │
         ▼
  OOD check (1 LLM, prompt minimal)
         │
    "no" │  "yes"
         │    │
         │    ▼
         │  Router (simple | agent)
         │    │              │
         │    ▼              ▼
         │  simple         agent
         │    │              │
         │  _node_rewrite  _rewrite_question()  ← PARTAGÉ
         │  (via helper)     │
         │    │              ▼
         │  retrieve       ReAct (question reformulée)
         │  grade
         │  generate
         │
         ▼
  Réponse OOD immédiate
  (route = "out_of_domain")
```

---

### 9.5 Fichiers modifiés dans cette session

| Fichier | Nature de la modification |
|---------|--------------------------|
| `src/llm/gemini_client.py` | Fix détection Gemma (`gemma-3` → `gemma`) |
| `src/agents/rag_agent.py` | Fix snippets KB + web, ajout OOD check, ajout rewrite partagé |
| `src/agents/react_agent.py` | Fix snippets ReAct tronqués |
| `config/prompts.yaml` | Ajout prompt `ood_check_system` |
| `backend/routers/chat.py` | Fix cartesian product SQLAlchemy + import `datetime` |
