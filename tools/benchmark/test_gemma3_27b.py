"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  TEST — gemma-3-27b-it                                                       ║
║  Catégorie : LLM local léger (Gemma 3) | RPD: 14 400 | RPM: 30              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  UTILITÉ POUR TON AGENTIC RAG :                                              ║
║  → MEILLEUR VOLUME : 14 400 RPD = ~2 880 questions/jour                      ║
║  → Idéal phase dev : itérer prompts, tester chunking, améliorer le grading   ║
║  → 128K tokens de contexte — adapté à tes 101 books                          ║
║  → Test spécifique : stress test avec 10 appels consécutifs                  ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage :
    python -m scripts.test_gemma3_27b
    python -m scripts.test_gemma3_27b --stress   # teste 10 appels pour RPM
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

MODEL = "gemma-3-27b-it"
RPD = 14_400
RPM = 30

# Exemples de questions issues de ton corpus 101 books
SAMPLE_QUESTIONS_ML = [
    "What is the difference between bagging and boosting in ensemble methods?",
    "Explain the bias-variance tradeoff with a concrete example.",
    "How does cross-validation prevent data leakage?",
    "What are the assumptions of linear regression?",
    "Describe the ROC curve and AUC metric.",
]

SAMPLE_CONTEXT = """
[source: sklearn_user_guide.pdf | page: 89]
Ensemble methods combine multiple base estimators to improve generalization.
Bagging (Bootstrap Aggregating) trains multiple models on random subsets of training data
with replacement. Each model is trained independently. Random Forest is a bagging ensemble
of decision trees that also uses feature randomness.

Boosting trains models sequentially, where each model focuses on the errors of the previous.
AdaBoost, Gradient Boosting (GBM), XGBoost, and LightGBM are popular boosting methods.
Boosting generally achieves lower bias but can overfit more than bagging.

[source: pattern_recognition_bishop.pdf | page: 149]
The bias-variance decomposition shows that expected prediction error decomposes into
irreducible noise, bias² (error from wrong assumptions), and variance (sensitivity to
training data fluctuations). High bias → underfitting. High variance → overfitting.
The optimal model minimizes bias² + variance.
"""

RAG_SYSTEM = """You are an expert assistant in data science, machine learning, and artificial intelligence.
Answer the user's question using ONLY the provided context.
CRITICAL: Always respond in the SAME language as the user's question.
If the context is insufficient, say so explicitly. Do not invent.
Prefer concise, precise, technical answers."""

GRADE_SYSTEM = """You are a grader assessing relevance of a retrieved document to a user question.
Output a single word: "yes" or "no"."""

REWRITE_SYSTEM = """Rewrite the question into a standalone query for vector search.
Keep the same language. Output only the rewritten question."""


def run_test(stress: bool = False):
    cfg = get_settings()
    if not cfg.gemini_api_key:
        print("❌ GEMINI_API_KEY manquant dans .env")
        sys.exit(1)

    llm = ChatGoogleGenerativeAI(
        model=MODEL,
        google_api_key=cfg.gemini_api_key,
        temperature=0.2,
        max_output_tokens=1024,
        top_p=0.95,
    )

    print(f"\n{'='*65}")
    print(f"  🤖  TEST MODÈLE : {MODEL}")
    print(f"  📊  RPD: {RPD:,} | RPM: {RPM}")
    print(f"  🎯  Profil : Volume maximal pour dev/test intensif")
    print(f"{'='*65}\n")

    # ── TEST 1 : REWRITE ──────────────────────────────────────────────────────
    print("🔄 [1/4] TEST REWRITE\n")
    history = "USER: What is a decision tree?\nASSISTANT: A decision tree splits data..."
    followup = "How is it different from random forest?"

    msgs = [
        SystemMessage(content=REWRITE_SYSTEM),
        HumanMessage(content=f"History:\n{history}\n\nQuestion: {followup}"),
    ]
    t0 = time.perf_counter()
    result = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    rewritten = (result.content if isinstance(result.content, str) else str(result.content)).strip()

    print(f"   📥 Original : '{followup}'")
    print(f"   📤 Rewritten : '{rewritten}'")
    print(f"   ⏱  {lat:.2f}s\n")
    time.sleep(1)

    # ── TEST 2 : GRADING ─────────────────────────────────────────────────────
    print("🎯 [2/4] TEST GRADING\n")
    cases = [
        (SAMPLE_CONTEXT[:400], "What is the difference between bagging and boosting?", "yes"),
        ("Python was created in 1991 by Guido van Rossum and features clean syntax.", "What is bagging in ML?", "no"),
        (SAMPLE_CONTEXT[450:], "Explain bias-variance tradeoff", "yes"),
    ]

    correct = 0
    for doc, q, expected in cases:
        msgs = [
            SystemMessage(content=GRADE_SYSTEM),
            HumanMessage(content=f"Document:\n{doc[:400]}\n\nQuestion: {q}\n\nRelevant?"),
        ]
        t0 = time.perf_counter()
        result = llm.invoke(msgs)
        lat = time.perf_counter() - t0
        verdict = (result.content if isinstance(result.content, str) else str(result.content)).strip().lower()
        ok = verdict.startswith(expected)
        correct += int(ok)
        icon = "✅" if ok else "❌"
        print(f"   {icon} '{verdict[:10]}' (attendu: '{expected}') | {lat:.2f}s")
        time.sleep(1)

    print(f"\n   📊 Score grading : {correct}/3\n")
    time.sleep(2)

    # ── TEST 3 : GÉNÉRATION ───────────────────────────────────────────────────
    print("💬 [3/4] TEST GÉNÉRATION\n")
    question = "Quelle est la différence entre bagging et boosting ? Lequel choisir et pourquoi ?"
    print(f"   ❓ {question}\n")

    msgs = [
        SystemMessage(content=RAG_SYSTEM),
        HumanMessage(content=f"Context:\n---\n{SAMPLE_CONTEXT}\n---\n\nQuestion: {question}\n\nAnswer:"),
    ]
    t0 = time.perf_counter()
    result = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    answer = result.content if isinstance(result.content, str) else str(result.content)

    print(f"   📝 ({len(answer)} chars, {lat:.2f}s) :\n")
    print("   " + "\n   ".join(answer.strip().split("\n")[:12]))
    time.sleep(2)

    # ── TEST 4 : STRESS TEST (RPM) ────────────────────────────────────────────
    if stress:
        print(f"\n⚡ [4/4] STRESS TEST — 10 appels rapides (limite RPM={RPM})\n")
        print("   Objectif : Mesurer la latence réelle et détecter les throttling.\n")
        latencies = []
        errors = 0
        for i in range(10):
            q = SAMPLE_QUESTIONS_ML[i % len(SAMPLE_QUESTIONS_ML)]
            msgs = [HumanMessage(content=f"Answer in 1 sentence: {q}")]
            try:
                t0 = time.perf_counter()
                llm.invoke(msgs)
                lat = time.perf_counter() - t0
                latencies.append(lat)
                print(f"   [{i+1:02d}/10] ✅ {lat:.2f}s — {q[:50]}...")
            except Exception as e:
                errors += 1
                print(f"   [{i+1:02d}/10] ❌ {str(e)[:60]}")
            time.sleep(0.5)  # 0.5s entre appels

        if latencies:
            avg = sum(latencies) / len(latencies)
            print(f"\n   📊 Résultats stress test :")
            print(f"      Appels réussis : {len(latencies)}/10")
            print(f"      Erreurs 429   : {errors}")
            print(f"      Latence moy.  : {avg:.2f}s")
            print(f"      Min/Max       : {min(latencies):.2f}s / {max(latencies):.2f}s")
    else:
        print(f"\n💡 [4/4] STRESS TEST disponible")
        print(f"   Relance avec --stress pour tester les 10 appels consécutifs.\n")

    print(f"\n{'='*65}")
    print(f"  🚀 {MODEL} — Tests terminés")
    print(f"  📊 Grading : {correct}/3")
    print(f"  💡 RECOMMANDÉ pour : phase dev — itération rapide sur prompts/chunks")
    print(f"  📈 Capacité : ~{RPD // 5:,} questions/jour")
    print(f"{'='*65}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stress", action="store_true", help="Lance le stress test RPM")
    args = parser.parse_args()
    try:
        run_test(stress=args.stress)
    except KeyboardInterrupt:
        print("\n⛔ Interrompu.")
    except Exception as e:
        err = str(e)
        print(f"\n❌ Erreur : {err}")
        if "429" in err:
            print("⚠️  Quota dépassé.")


if __name__ == "__main__":
    main()
