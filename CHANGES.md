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

---

## 23 Mai 2026 — Corrections architecturales CRAG + ReAct

> **Objectif** : corriger les fautes architecturales identifiées dans le pipeline CRAG-light et le chemin ReAct après une analyse approfondie du code. Les corrections portent sur la pureté des nœuds LangGraph, l'efficacité de la boucle de retry CRAG, la robustesse du parsing du grader, la qualité du prompt de grading, et l'affichage des sources du chemin ReAct.

---

### 10.1 Corrections implémentées

---

#### A. `history` dans le state LangGraph — `src/agents/rag_agent.py`

**Problème détecté :** Le nœud `_node_rewrite` lisait `self.memory.history()` directement — un objet externe mutable partagé. Un nœud LangGraph doit être une fonction pure (`state_in → state_out`), sans dépendances cachées sur des objets extérieurs. Ce couplage rendait le graphe non-reproductible et impossible à tester unitairement.

**Correction :**
- Ajout du champ `history: list[dict]` dans `RagState` (snapshot de la mémoire, injecté une seule fois à l'entrée du graphe).
- Dans `_run_simple()` : `prior_history = self.memory.history()[:-1]` injecté dans l'état initial — c'est le seul endroit où `self.memory` est lu pour l'historique.
- Dans `_node_rewrite` : lecture de `state.get("history", [])` au lieu de `self.memory.history()`.

---

#### B. Boucle de retry CRAG inutile — `src/agents/rag_agent.py` + `config/prompts.yaml`

**Problème détecté :** Quand `_decide_after_grade` renvoyait vers `rewrite` (0 documents pertinents), le nœud `_node_rewrite` recevait exactement les mêmes inputs qu'à l'itération précédente — même `state["question"]` (original, inchangé), même `self.memory` (inchangé). Le LLM produisait donc la même réécriture → mêmes documents → même grading → web fallback sans avoir vraiment réessayé. Deux appels LLM gaspillés.

**Correction :**
- `_node_rewrite` détecte maintenant `is_retry = state.get("iterations", 0) > 0`.
- Sur le premier passage : comportement identique à avant (rewrite contextuel avec historique).
- Sur un retry : utilisation d'un prompt dédié `reformulate_retry_user` qui indique explicitement au LLM que la query précédente `{previous_query}` a échoué et lui demande un angle complètement différent (synonymes, scope plus large/plus étroit, reformulation en définition, etc.).
- `previous_query` est lu depuis `state.get("rewritten_question")` — la réécriture qui a déjà échoué.

**Nouveau prompt ajouté :** `reformulate_retry_user` dans `config/prompts.yaml`.

---

#### C. Parsing fragile du grader — `src/agents/rag_agent.py`

**Problème détecté :** La ligne `decisions.append("yes" in line)` cherchait le mot "yes" n'importe où dans la ligne. Une réponse LLM comme `"no, this is not a yes for this query"` était parsée comme `True` (faux positif) car "yes" apparaît dans la justification négative. Les documents non pertinents passaient le grading silencieusement.

**Correction :** Remplacement par deux regex compilées qui vérifient que "yes" ou "no" est le **premier mot significatif** de la ligne, en tolérant un numéro et une ponctuation optionnels en préfixe (`"1. yes"`, `"2) no"`, `"3: yes"`). Le `\b` (word boundary) empêche de matcher "yesterday". Toute ligne non parseable → `False` par défaut (comportement conservateur).

```python
_YES = re.compile(r"^\s*\d*\s*[.):\-]?\s*yes\b", re.IGNORECASE)
_NO  = re.compile(r"^\s*\d*\s*[.):\-]?\s*no\b",  re.IGNORECASE)
```

---

#### D. Prompt de grading trop vague — `config/prompts.yaml`

**Problème détecté :** Le `grade_batch_system` actif était commenté (aucun prompt actif pour le grader). L'ancien prompt commenté ne définissait aucun critère de pertinence — le LLM devait deviner sur quelle base décider. Dans une base entièrement ML/AI, presque tout est "lié" au sujet → grading trop permissif, filtrage inefficace.

**Correction :** Nouveau `grade_batch_system` actif avec :
- Critère explicite : `"DIRECTLY helps answer"` au lieu de rien.
- Distinction claire : "mentionner le sujet" ≠ "aider à répondre".
- Exemple concret du domaine : CNNs ≠ Random Forests même si les deux sont ML.
- Format de sortie inchangé (liste numérotée yes/no).
- Ancien prompt conservé commenté comme référence.

---

#### E. Sources du chemin ReAct — `src/agents/react_agent.py`

**Problème détecté :** Les sources retournées par le chemin ReAct affichaient le nom de l'outil (`search_knowledge_base`) comme `book_title` au lieu du vrai titre du livre. Le texte formaté par `_format_results` contenait les vraies références `[Deep Learning — Goodfellow, p.127]` dans le snippet mais elles n'étaient pas extraites en champs structurés. Le chemin CRAG retournait des sources propres ; le chemin ReAct des sources inutilisables — incohérence de qualité.

**Correction :**
- Ajout de la fonction `_parse_tool_sources(tool_text, tool_name)` qui découpe le texte formaté en blocs (séparateur `\n\n---\n\n`) et extrait le `book_title` et la `page` de chaque header `[...]` via la regex `_HEADER_RE`.
- Le tool `search_web` est traité séparément (format différent) → `book_title = "Web"`.
- Fallback sur le nom de l'outil si le parsing échoue sur un bloc.
- Au lieu d'une source par appel outil → une source par chunk retourné (plus granulaire).

---

#### F. Icône Globe/Livre incorrecte — `frontend/src/pages/Chat.jsx`

**Problème détecté :** La logique `isWeb` du composant `SourceCard` détectait `<tool:` dans le champ `source` pour afficher l'icône Globe 🌐. Résultat : les sources KB (livres) affichaient une icône Globe, et les résultats web affichaient une icône Livre après la correction E.

**Correction :** La détection `isWeb` utilise maintenant `book_title === "Web"` (valeur explicite retournée par le tool web) plutôt que de chercher `<tool:` dans le champ `source`.

```javascript
// Avant
source.source?.includes("tool:") || source.source?.includes("<tool:")
// Après
source.book_title === "Web" || source.source === "search_web"
```

---

### 10.2 Critiques identifiées, discutées, non implémentées

#### AMBIGUOUS grade + Knowledge Refinement (CRAG paper)
**Problème :** Le papier CRAG original définit 3 grades (CORRECT / INCORRECT / AMBIGUOUS). L'implémentation actuelle n'a que yes/no. Les chunks partiellement pertinents sont soit gardés entiers (bruit dans le contexte) soit jetés (perte d'information). La "knowledge refinement" — extraire uniquement les phrases pertinentes d'un chunk AMBIGUOUS — est la contribution centrale de CRAG et est absente.

**Raison du report :** Chaque chunk AMBIGUOUS nécessite un appel LLM supplémentaire pour l'extraction. Avec 5 chunks potentiellement AMBIGUOUS, le coût en tokens et RPM est significatif sur un free tier. **Reporté au lendemain** pour décider de la stratégie (limiter le nombre de chunks raffinés, utiliser un modèle plus petit, ou tout faire en un seul appel batch).

#### Outils redondants dans le ReAct agent (Critique 8)
**Problème :** `search_by_category`, `search_by_level`, et `search_with_filters` se chevauchent — `search_with_filters` peut faire les deux premiers avec ses paramètres optionnels. Le LLM appelle souvent les deux séparément au lieu d'utiliser `search_with_filters` une seule fois, gaspillant du budget outil.

**Statut :** Identifié, non implémenté.

---

### 10.3 Paramètres intentionnellement en mode développement

Ces valeurs sont volontairement non-production pendant la phase de dev :

| Paramètre | Valeur actuelle | Valeur production recommandée |
|-----------|-----------------|-------------------------------|
| `agent.react.timeout_s` | `999999` | `60` |
| `online_eval.sample_rate` | `1.0` | `0.15` |

---

### 10.4 Code mort identifié

Les prompts `grade_system` et `grade_user` dans `config/prompts.yaml` ne sont appelés nulle part dans le code — vestiges d'une ancienne implémentation de grading document par document avant le batch grading. Peuvent être supprimés ou conservés comme référence.

---

### 10.5 Fichiers modifiés dans cette session

| Fichier | Nature de la modification |
|---------|--------------------------|
| `src/agents/rag_agent.py` | Ajout `history` dans `RagState`, injection dans `_run_simple`, refactor `_node_rewrite` (pureté + retry), fix parsing regex grader, import `re` |
| `src/agents/react_agent.py` | Ajout `_parse_tool_sources()`, `_HEADER_RE`, import `re` |
| `config/prompts.yaml` | Ajout `reformulate_retry_user`, nouveau `grade_batch_system` actif |
| `frontend/src/pages/Chat.jsx` | Fix logique `isWeb` dans `SourceCard` |
