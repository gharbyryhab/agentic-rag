"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  COMPARAISON FINALE — Choix du modèle pour l'Agentic RAG                     ║
║  Lit les résultats du benchmark et donne une recommandation personnalisée    ║
╚══════════════════════════════════════════════════════════════════════════════╝

Ce script :
  1. Lit le fichier results/benchmark_results.json généré par benchmark_all_models.py
  2. Affiche un tableau comparatif complet
  3. Recommande la configuration optimale pour ton RAG

Usage :
    # D'abord lancer le benchmark :
    python -m scripts.benchmark_all_models --skip-high-quality

    # Puis analyser les résultats :
    python -m scripts.compare_models
    python -m scripts.compare_models --json results/benchmark_results.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # ← parents[2] car on est 2 niveaux plus profondsys.path.insert(0, str(ROOT))

# Quotas de référence (RPD)
QUOTA_INFO = {
    "gemini-2.5-flash": 20,
    "gemini-flash-latest": 20,
    "gemini-3-flash-preview": 20,
    "gemini-2.5-flash-lite": 20,
    "gemini-3.1-flash-lite-preview": 500,
    "gemma-4-26b-it": 1_500,
    "gemma-4-31b-it": 1_500,
    "gemma-3-27b-it": 14_400,
    "gemma-3-12b-it": 14_400,
    "gemma-3-4b-it": 14_400,
    "gemma-3-1b-it": 14_400,
}

# Utilité spécifique par modèle pour l'Agentic RAG
MODEL_ROLES = {
    "gemini-2.5-flash":            "🥇 Gold standard (prod seulement)",
    "gemini-3-flash-preview":      "🥇 Gold standard nouvelle génération",
    "gemini-flash-latest":         "🥇 Alias gold standard",
    "gemini-2.5-flash-lite":       "⚡ Rapide mais quota trop faible",
    "gemini-3.1-flash-lite-preview": "💰 Grading économique (500 RPD)",
    "gemma-4-26b-it":              "🏆 Dev + prod — meilleur rapport qualité/quota",
    "gemma-4-31b-it":              "🏆 Meilleure qualité Gemma 4 (même quota)",
    "gemma-3-27b-it":              "🚀 Volume maximal dev (14K RPD)",
    "gemma-3-12b-it":              "📌 Modèle actuel — remplacer par Gemma 4",
    "gemma-3-4b-it":               "⚠️  Grading simple uniquement",
    "gemma-3-1b-it":               "❌ Trop léger pour ML technique",
}


def load_results(json_path: Path) -> list[dict]:
    if not json_path.exists():
        print(f"❌ Fichier introuvable : {json_path}")
        print(f"   Lance d'abord : python -m scripts.benchmark_all_models --skip-high-quality")
        return []
    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("results", [])


def compute_daily_capacity(rpd: int) -> str:
    if rpd < 30:
        return f"~{rpd // 5} questions/jour ⛔"
    elif rpd <= 500:
        return f"~{rpd // 5} questions/jour ⚠️"
    elif rpd <= 2000:
        return f"~{rpd // 5} questions/jour ✅"
    else:
        return f"~{rpd // 5:,} questions/jour 🚀"


def get_grade_accuracy(r: dict) -> str:
    tests = r.get("tests", {})
    total = 0
    correct = 0
    for key in ["grade_relevant", "grade_irrelevant"]:
        t = tests.get(key, {})
        if t.get("status") == "OK":
            total += 1
            if t.get("correct"):
                correct += 1
    if total == 0:
        return "N/A"
    return f"{correct}/{total}"


def get_gen_quality(r: dict) -> str:
    t = r.get("tests", {}).get("generation", {})
    if t.get("status") != "OK":
        return "N/A"
    score = t.get("total_score", 0)
    return f"{score}/4"


def get_avg_latency(r: dict) -> str:
    lats = []
    for t in r.get("tests", {}).values():
        if isinstance(t, dict) and "latency_s" in t:
            lats.append(t["latency_s"])
    if not lats:
        return "N/A"
    return f"{sum(lats)/len(lats):.1f}s"


def print_comparison_table(results: list[dict]):
    print(f"\n{'═'*110}")
    print(f"  📊  TABLEAU COMPARATIF — AGENTIC RAG ML/DS/AI")
    print(f"{'═'*110}")
    print(f"  {'Modèle':<32} {'RPD':>7} {'Capacité/jour':<24} {'Grade':>7} {'Génération':>12} {'Latence':>9}  Rôle")
    print(f"{'─'*110}")

    # Trier par score global décroissant
    sorted_r = sorted(results, key=lambda x: (x.get("overall_score", 0), QUOTA_INFO.get(x["model"], 0)), reverse=True)

    for r in sorted_r:
        model = r["model"]
        rpd = QUOTA_INFO.get(model, r.get("rpd", "?"))
        status = r.get("status", "OK")

        if status in ("QUOTA_DAY", "MODEL_NOT_FOUND", "ERROR"):
            status_icon = "⛔" if "QUOTA" in status else "❓"
            print(f"  {status_icon} {model:<30} {str(rpd):>7}   [{status}]")
            continue

        capacity = compute_daily_capacity(rpd) if isinstance(rpd, int) else "?"
        grade = get_grade_accuracy(r)
        gen = get_gen_quality(r)
        lat = get_avg_latency(r)
        role = MODEL_ROLES.get(model, "")[:35]

        score = r.get("overall_score", 0)
        max_s = r.get("max_score", 14)
        score_str = f"{score}/{max_s}"

        print(f"  {model:<32} {str(rpd):>7}   {capacity:<24} {grade:>7} {gen:>12} {lat:>9}  {role}")

    print(f"{'─'*110}")


def print_recommendations(results: list[dict]):
    # Trouver le meilleur modèle dans chaque quota range
    ok_results = [r for r in results if r.get("status") == "OK"]
    if not ok_results:
        print("\n❌ Aucun résultat disponible pour recommander.")
        return

    # Top par score parmi ceux > 20 RPD
    high_quota = [r for r in ok_results if QUOTA_INFO.get(r["model"], 0) > 20]
    high_quota_sorted = sorted(high_quota, key=lambda x: x.get("overall_score", 0), reverse=True)

    print(f"\n{'═'*80}")
    print(f"  🎯  RECOMMANDATIONS PERSONNALISÉES — TON AGENTIC RAG")
    print(f"{'═'*80}\n")

    print(f"  📋 Contexte : RAG spécialisé ML/DS/AI | 101 books | ~5 appels LLM/question\n")

    if high_quota_sorted:
        best = high_quota_sorted[0]
        rpd_best = QUOTA_INFO.get(best["model"], 0)

        print(f"  🏆 MEILLEUR MODÈLE TESTÉ (score + quota) :")
        print(f"     → {best['model']}")
        print(f"     → Score : {best.get('overall_score', 0)}/{best.get('max_score', 14)}")
        print(f"     → Capacité : ~{rpd_best // 5} questions/jour")
        print(f"     → Rôle : {MODEL_ROLES.get(best['model'], '')}")

    print(f"""
  📐 CONFIGURATION RECOMMANDÉE :

  ┌─────────────────────────────────────────────────────────────┐
  │  OPTION A — Mono-modèle (simple à gérer)                    │
  │                                                             │
  │  config.yaml → model_name: gemma-4-26b-it                   │
  │  Tous les appels : rewrite + grade + generate               │
  │  Quota : 1 500 RPD → ~300 questions/jour                    │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  OPTION B — Hybride (optimal qualité/quota)                 │
  │                                                             │
  │  GRADING   → gemini-3.1-flash-lite-preview (500 RPD)        │
  │  REWRITE   → gemma-3-27b-it (14 400 RPD)                    │
  │  GENERATE  → gemma-4-26b-it (1 500 RPD)                     │
  │                                                             │
  │  Implémentation : modifier src/agents/rag_agent.py          │
  │  pour instancier des LLM différents par nœud LangGraph      │
  └─────────────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────────────┐
  │  OPTION C — Dev intensif (itération rapide)                 │
  │                                                             │
  │  config.yaml → model_name: gemma-3-27b-it                   │
  │  14 400 RPD → ~2 880 questions/jour                         │
  │  Passe à gemma-4-26b-it une fois les prompts stabilisés     │
  └─────────────────────────────────────────────────────────────┘
""")

    print(f"  ⚠️  ÉVITER pour le dev :")
    print(f"     gemini-2.5-flash, gemini-3-flash → 20 RPD = ~4 questions/jour")
    print(f"     gemma-3-1b-it, gemma-3-4b-it → trop faibles pour ML technique")

    print(f"\n  🔧 Pour changer de modèle, édite config/config.yaml :")
    print(f"     llm:")
    print(f"       model_name: gemma-4-26b-it  # ← changer ici")
    print(f"\n  📊 Relance le benchmark après changement pour valider :")
    print(f"     python -m scripts.benchmark_all_models --skip-high-quality\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json",
        default="results/benchmark_results.json",
        help="Chemin vers le fichier de résultats JSON"
    )
    args = parser.parse_args()

    json_path = ROOT / args.json
    results = load_results(json_path)

    if not results:
        print("\n⚠️  Aucun résultat à analyser.")
        print("   Lance d'abord : python -m scripts.benchmark_all_models --skip-high-quality")
        sys.exit(1)

    print(f"\n📅 Résultats chargés depuis : {json_path}")
    print(f"   {len(results)} modèle(s) testés\n")

    print_comparison_table(results)
    print_recommendations(results)


if __name__ == "__main__":
    main()
