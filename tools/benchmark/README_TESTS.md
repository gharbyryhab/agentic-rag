# 🧪 Scripts de Test — Modèles Gemini/Gemma pour l'Agentic RAG

Tous les scripts se lancent depuis la **racine du projet** avec `python -m scripts.<nom>`.

---

## 📁 Organisation des scripts

```
scripts/
├── benchmark_all_models.py     ← Lance TOUS les modèles d'un coup
├── test_gemma4_26b.py          ← Test Gemma 4 26B (RECOMMANDÉ dev)
├── test_gemma4_31b.py          ← Test Gemma 4 31B (meilleure qualité)
├── test_gemma3_27b.py          ← Test Gemma 3 27B (volume max)
├── test_gemma3_12b.py          ← Test Gemma 3 12B (modèle actuel)
├── test_gemini_flash_lite.py   ← Test Flash Lite (grading spécialisé)
├── test_gemini_flash.py        ← Test Gemini 2.5/3 Flash (gold standard)
├── test_gemma3_small.py        ← Test Gemma 3 4B + 1B (modèles légers)
└── compare_models.py           ← Analyse les résultats du benchmark
```

---

## 🚀 Ordre recommandé pour tester

### Étape 1 — Benchmark complet (sans les 20 RPD)
```bash
python -m scripts.benchmark_all_models --skip-high-quality
```

### Étape 2 — Tests individuels approfondis
```bash
# Ton modèle actuel (référence)
python -m scripts.test_gemma3_12b

# Candidat principal
python -m scripts.test_gemma4_26b

# Variante qualité supérieure
python -m scripts.test_gemma4_31b

# Volume maximal pour dev
python -m scripts.test_gemma3_27b --stress

# Grading économique
python -m scripts.test_gemini_flash_lite

# Modèles légers (verdict rapide)
python -m scripts.test_gemma3_small
```

### Étape 3 — Gold standard (ÉCONOMISE le quota 20 RPD)
```bash
# UN seul appel — établit la référence qualité
python -m scripts.test_gemini_flash --gold-standard
```

### Étape 4 — Analyse des résultats
```bash
python -m scripts.compare_models
```

---

## 📊 Tableau récapitulatif des modèles

| Modèle | RPD | Questions/jour | Usage optimal |
|--------|-----|----------------|---------------|
| `gemini-2.5-flash` | 20 | ~4 | Production/démo uniquement |
| `gemini-3-flash-preview` | 20 | ~4 | Production/démo uniquement |
| `gemini-3.1-flash-lite-preview` | 500 | ~100 | Grading (yes/no) économique |
| `gemma-4-26b-it` | 1 500 | ~300 | **Dev + prod recommandé** |
| `gemma-4-31b-it` | 1 500 | ~300 | Qualité max Gemma 4 |
| `gemma-3-27b-it` | 14 400 | ~2 880 | **Tests intensifs dev** |
| `gemma-3-12b-it` | 14 400 | ~2 880 | Modèle actuel (à remplacer) |
| `gemma-3-4b-it` | 14 400 | ~2 880 | Grading simple uniquement |
| `gemma-3-1b-it` | 14 400 | ~2 880 | ❌ Trop faible |

---

## 🔧 Changer de modèle

Édite `config/config.yaml` :

```yaml
llm:
  model_name: gemma-4-26b-it   # ← changer ici
```

---

## 📂 Résultats

Les résultats JSON sont sauvegardés dans `results/benchmark_results.json`.

```bash
# Relancer l'analyse sans refaire le benchmark
python -m scripts.compare_models --json results/benchmark_results.json
```
