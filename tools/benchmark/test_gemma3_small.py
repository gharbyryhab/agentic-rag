"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  TEST — gemma-3-4b-it  +  gemma-3-1b-it  (modèles légers)                   ║
║  Catégorie : LLM local léger (Gemma 3) | RPD: 14 400 | RPM: 20/30           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  UTILITÉ POUR TON AGENTIC RAG :                                              ║
║  → Test rapide pour CONFIRMER que ces modèles sont trop faibles              ║
║  → Seule utilité potentielle : grading ultra simple (yes/no)                 ║
║  → Résultats attendus : faible qualité de génération sur ML technique        ║
║  → Ce script génère un verdict clair : utiliser ou éviter ?                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage :
    python -m scripts.test_gemma3_small
    python -m scripts.test_gemma3_small --model gemma-3-4b-it
    python -m scripts.test_gemma3_small --model gemma-3-1b-it
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # ← parents[2] car on est 2 niveaux plus profond
sys.path.insert(0, str(ROOT))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.config import get_settings

MODELS_INFO = {
    "gemma-3-4b-it": {
        "rpd": 14_400,
        "rpm": 20,
        "profile": "Léger, tâches simples — 4B paramètres",
        "expected_verdict": "⚠️ Grading OK, génération insuffisante pour ML technique",
    },
    "gemma-3-1b-it": {
        "rpd": 14_400,
        "rpm": 30,
        "profile": "Très léger, edge/mobile — 1B paramètres",
        "expected_verdict": "❌ Trop faible — uniquement yes/no trivial",
    },
    "gemma-3n-e4b-it": {
        "rpd": 14_400,
        "rpm": 20,
        "profile": "Variante 4B edge (alias)",
        "expected_verdict": "⚠️ Similaire au 4B",
    },
    "gemma-3n-e2b-it": {
        "rpd": 14_400,
        "rpm": 30,
        "profile": "Variante 2B edge (alias 1B)",
        "expected_verdict": "❌ Trop faible",
    },
}

# Tests — délibérément SIMPLES pour ces petits modèles
GRADE_SYSTEM = """You are a grader. Is the document relevant to the question?
Output only: "yes" or "no"."""

CONTEXT_SIMPLE = """
Neural networks are trained using backpropagation and gradient descent.
The loss function measures prediction error. Common loss functions: MSE for regression,
Cross-Entropy for classification. The optimizer updates weights to minimize loss.
"""

TESTS = [
    {
        "name": "Grading pertinent (facile)",
        "type": "grade",
        "doc": "Backpropagation computes gradients by applying the chain rule through layers.",
        "question": "How does backpropagation work?",
        "expected": "yes",
    },
    {
        "name": "Grading non pertinent (facile)",
        "type": "grade",
        "doc": "The Amazon river is the largest river by discharge volume in the world.",
        "question": "How does backpropagation work?",
        "expected": "no",
    },
    {
        "name": "Génération simple (1 concept)",
        "type": "generate",
        "question": "What is gradient descent in one sentence?",
        "min_quality": ["gradient", "minimize", "loss", "weights", "learning"],
    },
    {
        "name": "Génération technique (ML avancé)",
        "type": "generate",
        "question": "Explain the difference between batch normalization and layer normalization in transformers.",
        "min_quality": ["normalization", "batch", "layer", "transformer", "mean", "variance"],
    },
]


def test_single_model(model_name: str, api_key: str):
    info = MODELS_INFO.get(model_name, {"rpd": "?", "rpm": "?", "profile": "?"})

    print(f"\n{'─'*65}")
    print(f"  🤖 {model_name}")
    print(f"  📊 RPD: {info['rpd']:,} | RPM: {info['rpm']}")
    print(f"  📋 {info['profile']}")
    print(f"{'─'*65}\n")

    llm_grade = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.0,
        max_output_tokens=5,
    )
    llm_gen = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.2,
        max_output_tokens=300,
    )

    scores = {"grade": 0, "grade_total": 0, "gen_simple": 0, "gen_advanced": 0}

    for test in TESTS:
        t_name = test["name"]

        if test["type"] == "grade":
            scores["grade_total"] += 1
            msgs = [
                SystemMessage(content=GRADE_SYSTEM),
                HumanMessage(content=f"Document:\n{test['doc']}\nQuestion: {test['question']}\nRelevant?"),
            ]
            try:
                t0 = time.perf_counter()
                r = llm_grade.invoke(msgs)
                lat = time.perf_counter() - t0
                verdict = (r.content if isinstance(r.content, str) else str(r.content)).strip().lower()
                ok = verdict.startswith(test["expected"])
                scores["grade"] += int(ok)
                icon = "✅" if ok else "❌"
                print(f"  {icon} [{t_name}] → '{verdict[:10]}' (attendu: '{test['expected']}') | {lat:.2f}s")
            except Exception as e:
                print(f"  ❌ [{t_name}] ERREUR: {str(e)[:60]}")
            time.sleep(1)

        elif test["type"] == "generate":
            system = "Answer concisely and technically. Use only factual knowledge."
            msgs = [SystemMessage(content=system), HumanMessage(content=test["question"])]
            try:
                t0 = time.perf_counter()
                r = llm_gen.invoke(msgs)
                lat = time.perf_counter() - t0
                answer = (r.content if isinstance(r.content, str) else str(r.content)).strip()
                answer_lower = answer.lower()

                keywords_found = [kw for kw in test["min_quality"] if kw.lower() in answer_lower]
                quality_score = len(keywords_found) / len(test["min_quality"])
                is_simple = "simple" in t_name.lower()

                if quality_score >= 0.5:
                    icon = "✅"
                    if is_simple:
                        scores["gen_simple"] = 1
                    else:
                        scores["gen_advanced"] = 1
                elif quality_score >= 0.25:
                    icon = "⚠️ "
                else:
                    icon = "❌"

                print(f"  {icon} [{t_name}]")
                print(f"      Q: {test['question'][:60]}...")
                print(f"      A: {answer[:120]}{'...' if len(answer) > 120 else ''}")
                print(f"      Mots-clés : {keywords_found} ({quality_score:.0%})")
                print(f"      Latence : {lat:.2f}s")
            except Exception as e:
                print(f"  ❌ [{t_name}] ERREUR: {str(e)[:60]}")
            time.sleep(2)

    # ── VERDICT ───────────────────────────────────────────────────────────────
    grade_ok = scores["grade"] == scores["grade_total"]
    gen_simple_ok = scores["gen_simple"] == 1
    gen_advanced_ok = scores["gen_advanced"] == 1

    print(f"\n  📊 VERDICT {model_name} :")
    print(f"     Grading     : {'✅' if grade_ok else '❌'} {scores['grade']}/{scores['grade_total']}")
    print(f"     Génération simple  : {'✅' if gen_simple_ok else '❌'}")
    print(f"     Génération avancée : {'✅' if gen_advanced_ok else '❌'}")

    if grade_ok and gen_advanced_ok:
        verdict = "✅ UTILISABLE pour RAG ML — grading + génération"
        use_for = "grading + génération simple"
    elif grade_ok and gen_simple_ok:
        verdict = "⚠️  PARTIEL — grading OK, génération ML insuffisante"
        use_for = "grading uniquement (yes/no)"
    elif grade_ok:
        verdict = "⚠️  GRADING SEULEMENT — génération trop faible"
        use_for = "grading basique"
    else:
        verdict = "❌ DÉCONSEILLÉ pour ce RAG"
        use_for = "aucune tâche critique"

    print(f"\n     {verdict}")
    print(f"     → Utiliser pour : {use_for}")
    print(f"     → Attendu       : {info.get('expected_verdict', '?')}")

    return {
        "model": model_name,
        "grade_score": f"{scores['grade']}/{scores['grade_total']}",
        "gen_simple": gen_simple_ok,
        "gen_advanced": gen_advanced_ok,
        "verdict": verdict,
    }


def main():
    parser = argparse.ArgumentParser(description="Test modèles Gemma 3 légers")
    parser.add_argument(
        "--model",
        choices=list(MODELS_INFO.keys()),
        default=None,
        help="Modèle à tester (défaut: tous les 4)",
    )
    args = parser.parse_args()

    cfg = get_settings()
    if not cfg.gemini_api_key:
        print("❌ GEMINI_API_KEY manquant dans .env")
        sys.exit(1)

    models = [args.model] if args.model else list(MODELS_INFO.keys())

    print(f"\n{'='*65}")
    print(f"  🧪 TEST MODÈLES LÉGERS GEMMA 3 — {len(models)} modèle(s)")
    print(f"  Objectif : confirmer l'utilité pour grading vs génération")
    print(f"{'='*65}")

    results = []
    for model in models:
        try:
            r = test_single_model(model, cfg.gemini_api_key)
            results.append(r)
        except Exception as e:
            err = str(e)
            print(f"\n  ❌ {model} : {err[:80]}")
            if "404" in err:
                print(f"  ⚠️  Modèle introuvable — alias peut-être différent sur l'API")
        time.sleep(3)

    if len(results) > 1:
        print(f"\n\n{'='*65}")
        print(f"  📊 RÉCAPITULATIF MODÈLES LÉGERS")
        print(f"{'='*65}")
        for r in results:
            print(f"  {r['model']:<25} {r['verdict'][:50]}")
        print(f"\n  → Pour ton RAG ML : utilise ces modèles UNIQUEMENT pour le grading")
        print(f"  → Génération : passe à gemma-3-27b-it ou gemma-4-26b-it")


if __name__ == "__main__":
    main()
