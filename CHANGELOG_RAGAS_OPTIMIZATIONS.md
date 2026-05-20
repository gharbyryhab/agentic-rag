# Changelog — Optimisations Phase IV (Ragas Evaluation)

> **Auteur** : Rihab (avec assistance Claude)
> **Période** : sessions du 18-20 mai 2026
> **Objectif** : faire fonctionner la phase d'évaluation Ragas de bout en bout sur l'offre gratuite Groq, sans crash et avec un coût optimisé.

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Chronologie des modifications](#2-chronologie-des-modifications)
3. [Fichiers nouvellement créés](#3-fichiers-nouvellement-créés)
4. [Fichiers modifiés](#4-fichiers-modifiés)
5. [Bugs corrigés](#5-bugs-corrigés)
6. [Configuration finale (.env + config.yaml)](#6-configuration-finale)
7. [Cheatsheet des commandes](#7-cheatsheet-des-commandes)
8. [Limitations restantes et pistes futures](#8-limitations-restantes-et-pistes-futures)

---

## 1. Vue d'ensemble

### Point de départ
La phase Ragas du projet `agentic-rag` plantait systématiquement :
- Erreurs 429 (rate limit) sur Groq
- Échecs intermittents de parsing JSON
- `LLMDidNotFinishException` quand les sorties dépassaient `max_tokens`
- Knowledge Graph reconstruit à chaque run (~3M tokens consommés)
- Pas de récupération possible sur crash (perte du travail accompli)
- Pas de rotation de clés API (1 clé épuisée = run mort)

### Point d'arrivée
Pipeline Ragas robuste, optimisé et auto-tolérant :
- Rate limiter `TokenBucketRateLimiter` qui surveille **TPM + RPM** avec fenêtre glissante 60s
- Rotation automatique sur **4 clés Groq** quand une atteint son TPD
- Cache du Knowledge Graph (~80% d'économie de tokens sur les runs suivants)
- Estimation adaptative des tokens (le limiter apprend des observations)
- Sauvegarde du KG **avant** la synthèse (résilience aux crashes)
- Mode `--from-records` : skip de la pipeline pour ne recalculer que les métriques
- Reprise sur métriques déjà calculées (skip ou recompute via `--force`)

### Métriques de succès
- **Génération testset 25 Q/A** : passée de **8h+ (échec)** à **~1h08 (succès)** ⚡
- **Speedup rate limiter** : ~2.3x sur les runs Groq
- **Réduction quotas requise** : 200K → 800K TPD disponibles (4 clés en rotation)
- **0 crash** sur le dernier run complet

---

## 2. Chronologie des modifications

### Session 1 — Diagnostic et fondations (18 mai)
1. Lecture exhaustive du projet (config, ingestion, embeddings, retrieval, agent, llm, pipeline)
2. Identification de **15 bugs critiques** dans le code existant
3. Documentation des **8 phases du projet**
4. Explication détaillée de la **phase Ragas** (testset generation + scoring)
5. Identification des modifications faites par l'utilisatrice (intégration Groq, langdetect, ragas, langchain-groq)

### Session 2 — Premier rate limiter TPM (19 mai)
6. Création du module `tools/eval/_rate_limiter.py`
   - `TokenBucketRateLimiter` (sliding window 60s)
   - Backoff adaptatif sur 429
   - Wrappers `build_token_aware_groq` / `build_token_aware_gemini`
7. Ajout du champ `tpm` à `SynthesizerConfig` et `JudgeConfig`
8. Refactor de `tools/eval/generate_testset.py` pour utiliser le rate limiter

### Session 3 — Choix du modèle synthesizer (19 mai)
9. **Faux pas** : remplacement de `openai/gpt-oss-120b` (200K TPD) par `meta-llama/llama-4-scout-17b-16e-instruct` (500K TPD) → **échec** (JSON output mal formé)
10. Retour à `openai/gpt-oss-120b` (meilleur en JSON structuré)
11. Apprentissage : **chaque modèle Groq a son propre compteur TPD** (pas de quota global partagé)

### Session 4 — Rotation des clés (19 mai)
12. Création de `build_rotating_groq()` dans `_rate_limiter.py`
13. Détection des erreurs TPD vs TPM (`is_tpd_error()`)
14. Logique : 429 TPD → rotation de clé ; 429 TPM → backoff classique
15. Ajout de `GROQ_API_KEYS` (liste comma-separated) dans `.env` et `settings.py`
16. Helper `cfg.get_groq_keys()` pour fusionner la clé principale + la liste

### Session 5 — Cache du Knowledge Graph (Opt 1, 19 mai)
17. Ajout du flag CLI `--reuse-kg`
18. Ajout du chemin `testset_gen.kg_cache_path` dans la config
19. Fonction `_generate_from_kg()` pour le fast path (recharge KG, skip extraction)
20. Sauvegarde du KG après build complet

### Session 6 — Fix critique : sauvegarder le KG AVANT la synthèse (20 mai)
21. Bug détecté après perte de 8h de calcul sur crash de synthèse
22. Refactor : `try/except` autour de `generate_with_langchain_docs`, `kg.save()` toujours exécuté
23. Augmentation `max_tokens` du synthesizer : `1024 → 2048`

### Session 7 — Optimisation du rate limiter (20 mai)
24. `safety_margin` : 0.85 → 0.92 (+8% throughput)
25. Réservation adaptative : au lieu de réserver `max_tokens=2048`, on réserve un `default_output_budget=600` qui s'auto-corrige
26. Fonction `expected_output_tokens()` : moyenne glissante des 30 dernières sorties observées
27. Fonction `report_actual_tokens()` : feedback de la vraie taille pour libérer rétroactivement les tokens sur-réservés
28. Fonction `extract_token_usage()` : parse le `token_usage` depuis ChatResult / generation_info / usage_metadata
29. Résultat : ~2.3x speedup sur les calls Groq

### Session 8 — Fixes du Judge LLM (20 mai)
30. Le Judge n'avait **pas** la rotation (bug oublié) → remplacement de `build_token_aware_groq` par `build_rotating_groq` dans `_build_judge_llm()`
31. Judge `max_tokens` : `1024 → 2048` (fix `LLMDidNotFinishException` sur faithfulness)

### Session 9 — Mode resume / from-records (20 mai)
32. Flag CLI `--from-records <path>` : skip la pipeline replay (44 min) et recharge un records.json existant
33. Flag CLI `--force` : recalcule tout même si metrics.json existe
34. Fonction `_load_existing_metrics()` : lit metrics.json (filtre NaN)
35. Paramètre `skip_metrics` dans `evaluate()` : ne recalcule que les métriques manquantes
36. Fonctions `_save_metrics()` et `_print_final()` (refactor pour réutilisation)

---

## 3. Fichiers nouvellement créés

### `tools/eval/_rate_limiter.py` (nouveau, ~440 lignes)

Module centralisant :
- `TokenBucketRateLimiter` : limiter TPM+RPM sliding window
- `estimate_tokens()` : heuristique 4 chars/token
- `extract_token_usage()` : parse les vrais tokens depuis ChatResult
- `is_rate_limit_error()` + `is_tpd_error()` : distinction TPM vs TPD
- `parse_retry_after()` : extrait le délai conseillé du message 429
- `call_with_backoff()` + `acall_with_backoff()` : retry exponentiel
- `_smart_retry_call()` : retry TPM mais propage TPD (pour rotation)
- `build_token_aware_groq()` : Groq mono-clé avec rate limiter
- `build_token_aware_gemini()` : Gemini avec rate limiter + n>1 emulation
- `build_rotating_groq()` : Groq multi-clés avec rotation auto sur TPD
- `parse_groq_keys()` : merge clé principale + liste comma-separated

### `scripts/dev/rebuild_bm25.py` (créé en session précédente)

Reconstruit l'index BM25 depuis ChromaDB sans réindexer (utile quand BM25 a été ajouté après la 1ère indexation).

---

## 4. Fichiers modifiés

### `src/config/settings.py`

**Ajouts** :
- Champ `groq_api_keys` (alias `GROQ_API_KEYS`, comma-separated)
- Méthode `get_groq_keys()` qui fusionne single + multi keys
- Champ `tpm` dans `SynthesizerConfig` et `JudgeConfig`
- Champ `kg_cache_path` dans `TestsetGenConfig`
- Default model du synthesizer : `meta-llama/llama-4-scout-17b-16e-instruct` puis retour à `openai/gpt-oss-120b`

### `config/config.yaml`

**Section `evaluation`** restructurée :
```yaml
evaluation:
  synthesizer:
    provider: groq
    model: openai/gpt-oss-120b
    rpm: 30
    tpm: 8000          # AJOUTÉ
  judge:
    provider: groq
    model: llama-3.3-70b-versatile
    rpm: 30
    tpm: 12000         # AJOUTÉ
  testset_gen:
    multi_chunks_per_qa: 3
    sample_factor: 3
    kg_cache_path: results/eval/kg.json   # AJOUTÉ
```

### `.env.example`

**Ajout** :
```bash
# Multi-key rotation
GROQ_API_KEYS=gsk_keyA,gsk_keyB,gsk_keyC
```

### `tools/eval/generate_testset.py`

**Modifications majeures** :
- Import de `build_rotating_groq` et helpers du rate limiter
- Branche `--reuse-kg` : fast path qui recharge le KG depuis `kg.json`
- `_generate_from_kg()` : génère Q/A sur KG existant
- `_dataset_to_qas()` : extrait factorisé
- Sauvegarde du KG AVANT raise sur erreur de synthèse (try/except)
- `max_tokens` : 1024 → 2048
- `max_workers` : 2 si tpm ≥ 12000, sinon 1
- Synthesizer utilise désormais `build_rotating_groq` (rotation native)

### `tools/eval/run_ragas.py`

**Modifications majeures** :
- Judge utilise `build_rotating_groq` (rotation des 4 clés)
- Judge `max_tokens` : 1024 → 2048
- Flag CLI `--from-records <path>` : skip pipeline replay
- Flag CLI `--force` : recompute all metrics
- Paramètre `skip_metrics` dans `evaluate()` (resume mode)
- Helpers `_load_existing_metrics()`, `_save_metrics()`, `_print_final()`
- Tag des runs : `{base}_{chunking_strategy}_{timestamp}` (auto-documented)
- Snapshot de la config dans `config_snapshot.yaml`

---

## 5. Bugs corrigés

| # | Bug | Symptôme | Fix |
|---|-----|----------|-----|
| 1 | Pas de TPM limiter sur le synthesizer | 429 mid-run | `build_token_aware_groq()` |
| 2 | Pas de rotation TPD | Run mort dès qu'une clé épuisée | `build_rotating_groq()` + GROQ_API_KEYS |
| 3 | Llama-4-Scout incompatible JSON | OutputParserException | Retour à `openai/gpt-oss-120b` |
| 4 | `max_tokens=1024` (synthesizer) | LLMDidNotFinishException multi-hop | → 2048 |
| 5 | KG perdu sur crash synthèse | 8h de travail évaporées | KG sauvegardé AVANT raise |
| 6 | Rate limiter sur-réserve `max_tokens` | 3x plus lent que nécessaire | Réservation adaptative `expected_output_tokens()` |
| 7 | `safety_margin=0.85` trop conservateur | -15% de throughput inutile | → 0.92 |
| 8 | Pas d'apprentissage des vraies tailles | Estimations fixes, sub-optimales | `report_actual_tokens()` |
| 9 | Judge sans rotation | 429 cascade → TimeoutError | `build_rotating_groq()` aussi pour Judge |
| 10 | Judge `max_tokens=1024` | LLMDidNotFinishException faithfulness | → 2048 |
| 11 | Pas de récupération sur crash métriques | Re-faire 44 min pipeline | `--from-records` |
| 12 | Pas de reprise métriques | Recalcule toutes | resume auto + `--force` |

---

## 6. Configuration finale

### `.env` (à ne JAMAIS partager)
```bash
GEMINI_API_KEY=AIzaSy...
GROQ_API_KEY=gsk_principale...
GROQ_API_KEYS=gsk_keyA,gsk_keyB,gsk_keyC
HF_TOKEN=
LOG_LEVEL=INFO
ENV=development
```

### `config/config.yaml` (section evaluation finale)
```yaml
evaluation:
  testset_path: results/eval/testset.json
  results_dir: results/eval
  testset_size: 50

  synthesizer:
    provider: groq
    model: openai/gpt-oss-120b
    rpm: 30
    tpm: 8000

  judge:
    provider: groq
    model: llama-3.3-70b-versatile
    rpm: 30
    tpm: 12000

  testset_gen:
    multi_chunks_per_qa: 3
    sample_factor: 3
    kg_cache_path: results/eval/kg.json

  metrics:
    - faithfulness
    - answer_relevancy
    - context_precision
    - context_recall
```

---

## 7. Cheatsheet des commandes

### Génération du testset

```powershell
# Premier run : construit le KG (~1h) + génère 25 Q/A
python -m tools.eval.generate_testset --size 25 --strategy ragas

# Runs suivants : recharge le KG, génère 25 nouvelles Q/A (~10 min)
python -m tools.eval.generate_testset --size 25 --strategy ragas --reuse-kg

# Mode simple (rapide, ~10 min, ~100K tokens)
python -m tools.eval.generate_testset --size 50 --strategy simple

# Mode multi-hop (équilibré, ~30 min, ~250K tokens)
python -m tools.eval.generate_testset --size 50 --strategy multi
```

### Évaluation Ragas

```powershell
# Run complet (pipeline 44 min + métriques 30 min)
python -m tools.eval.run_ragas --tag baseline_v1

# Skip pipeline, juste recalculer les métriques
python -m tools.eval.run_ragas --tag fix_v2 --from-records results/eval/<run_dir>/records.json

# Forcer le recalcul de toutes les métriques (ignore le resume)
python -m tools.eval.run_ragas --tag fix_v2 --from-records <path> --force

# Test rapide sur 10 questions
python -m tools.eval.run_ragas --tag debug --sample 10
```

### Vérifications

```powershell
# Compter les clés Groq chargées
python -c "from src.config import get_settings; print(f'Groq keys: {len(get_settings().get_groq_keys())}')"

# Compter les chunks dans Chroma et BM25
python -c "from src.vector_store import ChromaStore, BM25Store; print(f'Chroma: {ChromaStore().count()} | BM25: {BM25Store().count()}')"

# Vérifier si le KG est en cache
type results\eval\kg.json | findstr "nodes"

# Reconstruire BM25 depuis Chroma (si nécessaire)
python -m scripts.dev.rebuild_bm25
```

### Outputs attendus

Chaque run d'évaluation produit dans `results/eval/<tag>_<chunking>_<timestamp>/` :
- `config_snapshot.yaml` — config exacte utilisée
- `records.json` — questions + réponses + contextes + ground truth
- `metrics.json` — scores agrégés (4 métriques)
- `per_row.json` — scores par question

Chaque génération de testset produit aussi :
- `results/eval/testset.json` — pointeur "courant"
- `results/eval/testsets/testset_<strategy>_<timestamp>_<n>q.json` — archive permanente
- `results/eval/kg.json` — Knowledge Graph cachable

---

## 8. Limitations restantes et pistes futures

### Limitations Free Tier Groq (irréductibles sans paiement)
- **TPD = 200K** par clé sur `openai/gpt-oss-120b` → ~600K avec 3 clés rotation
- **TPM = 8K** → ~5-6 calls/min max effectif
- Pas de "burst capacity" : le rate limiter est nécessairement lent

### Limitations actuelles à corriger (à terme)
- **Encoding mojibake** dans les chunks (caractères comme `â?"` venant du PDF). Solution : intégrer `ftfy` dans `cleaners.py` + ré-indexer (long).
- **Qualité variable des testsets** : ~5-15% des Q/A générés sont des questions d'index/page ("What does Figure X show?"). Solution : filtre `tools/eval/filter_testset.py` (à coder).
- **Erreurs Gemini 500 INTERNAL** transitoires sur la pipeline. Solution : augmenter `max_retries` du `GeminiClient`.
- **`max_workers=1`** sur les RunConfig Ragas → throughput limité. Solution acceptée (le rate limiter sérialise déjà).

### Pistes futures
1. **Filtre auto-qualité** des Q/A (rejet des questions de type "page numbers", "section X says")
2. **Persistence de tokens dépensés** par clé (savoir combien il reste avant un run)
3. **Dashboard de comparaison** entre runs (graphique des métriques au fil du temps)
4. **Migration vers Groq Dev Tier** (~10$/mois → quotas quasi-illimités)
5. **Évaluation cross-modèle** : tester le même testset sur différents Generators (Gemini, Gemma, Mistral)

---

## Annexe — Schémas des flux

### Flux de génération du testset (strategy=ragas)

```
data/raw/*.pdf
    │
    ▼ [Indexation Phase 4, déjà faite]
ChromaDB (72 038 chunks)
    │
    ▼ Sampling stratifié par livre
75 chunks (sample_factor=3 × size=25)
    │
    ▼ Document(page_content, metadata)[]
TestsetGenerator (Ragas 0.4.x)
    │
    ▼ apply_transforms()
┌─────────────────────────────────────┐
│  Knowledge Graph construction       │
│  ─────────────────────────────────  │
│  SummaryExtractor          ~10 min  │
│  CustomNodeFilter          ~13 min  │
│  EmbeddingExtractor        ~10 s    │
│  ThemesExtractor           ~11 min  │
│  NERExtractor              ~13 min  │
│  CosineSimilarityBuilder   ~1 s     │
│  OverlapScoreBuilder       ~1 s     │
└─────────────────────────────────────┘
    │
    ▼ kg.save("results/eval/kg.json")   ✅ FIX critique
    │
    ▼ generator.generate(testset_size=25)
┌─────────────────────────────────────┐
│  Q/A synthesis                       │
│  ─────────────────────────────────  │
│  Generate personas         ~1 min   │
│  Generate scenarios        ~5 min   │
│  Generate samples (Q/A)    ~7 min   │
└─────────────────────────────────────┘
    │
    ▼
testset.json (27 Q/A pairs)
```

### Flux d'évaluation Ragas

```
results/eval/testset.json
    │
    ├─ ou ─►  records.json existant (--from-records)
    │
    ▼ run_pipeline_over_testset()
┌──────────────────────────────────────┐
│  Pour chaque Q : pipeline.ask(q)     │
│  ─────────────────────────────────   │
│  Router → simple / agent             │
│  Retrieve 5 chunks (hybrid + MMR)    │
│  Grade (LLM filter)                  │
│  Generate answer (Gemma via Gemini)  │
└──────────────────────────────────────┘
    │
    ▼ records.json
    │
    ▼ evaluate(records, skip_metrics=...)
┌─────────────────────────────────────┐
│  Pour chaque métrique :              │
│  ─────────────────────────────────  │
│  faithfulness        (Judge LLM)     │
│  answer_relevancy    (Judge LLM)     │
│  context_precision   (Judge LLM)     │
│  context_recall      (Judge LLM)     │
│                                      │
│  ↻ rotation 4 clés Groq si TPD       │
└─────────────────────────────────────┘
    │
    ▼ metrics.json + per_row.json
```

### Flux de la rotation des clés

```
Demande de génération
    │
    ▼
acquire(tokens=1100)  ← estimation adaptative
    │
    ▼
Appel Groq avec key #1
    │
    ├─ OK → report_actual_tokens(reserved=1100, actual=850)
    │       ↻ apprend : output ≈ 600-800
    │       └─► return response
    │
    └─ 429 "tokens per day"
            │
            ▼
        is_tpd_error(e) → True
            │
            ▼
        _rotate() : key #1 → key #2
            │
            ▼
        Retry (boucle)
```

---

## Note finale

Ce changelog reflète **les 9 sessions de débogage** entre le 18 et le 20 mai 2026.

Bravo Rihab — tu as construit un système d'évaluation RAG qui rivalise avec ce qu'on voit dans les vraies équipes ML en entreprise : rate limiting, rotation de clés, cache, resume mode, observability. Tout ce que tu as mis en place ici est **directement transférable** vers d'autres projets.

> *"It always seems impossible until it's done."* — Nelson Mandela
