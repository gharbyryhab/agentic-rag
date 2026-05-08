"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  TEST — gemma-3-12b-it  (modèle actuel dans config.yaml)                     ║
║  Catégorie : LLM local léger (Gemma 3) | RPD: 14 400 | RPM: 30              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  UTILITÉ POUR TON AGENTIC RAG :                                              ║
║  → Ton modèle ACTUEL — contexte de référence pour comparaison                ║
║  → Même quota que 27B mais moins puissant                                    ║
║  → Suffisant pour le GRADING (yes/no) mais limite en génération complexe     ║
║  → Test de régression : vérifier que les scores actuels sont corrects        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage :
    python -m scripts.test_gemma3_12b
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # ← parents[2] car on est 2 niveaux plus profondsys.path.insert(0, str(ROOT))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.config import get_settings

MODEL = "gemma-3-12b-it"
RPD = 14_400
RPM = 30

SAMPLE_CONTEXT = """
[source: ml_fundamentals.pdf | page: 55]
A neural network consists of layers of interconnected neurons. Each neuron applies
a weighted sum of inputs followed by a non-linear activation function.
Common activations: ReLU (max(0,x)), Sigmoid (1/(1+e^-x)), Tanh.
Training uses backpropagation to compute gradients and gradient descent to update weights.

[source: feature_engineering_book.pdf | page: 102]
Feature scaling ensures that no single feature dominates due to its magnitude.
StandardScaler: z = (x - mean) / std. MinMaxScaler: x' = (x - min) / (max - min).
Tree-based models (Random Forest, XGBoost) don't require scaling.
Neural networks and SVM are sensitive to feature scale.
"""

RAG_SYSTEM = """You are an expert ML assistant. Answer using ONLY the provided context.
CRITICAL: Respond in the SAME language as the question. Do not invent."""

GRADE_SYSTEM = """Grader: is the document relevant to the question? Output only "yes" or "no"."""
REWRITE_SYSTEM = """Rewrite as a standalone query for vector search. Same language. Only the question."""


def run_test():
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
    print(f"  🤖  TEST MODÈLE : {MODEL}  [⭐ TON MODÈLE ACTUEL]")
    print(f"  📊  RPD: {RPD:,} | RPM: {RPM}")
    print(f"  📌  Profil : Modèle de référence — base de comparaison")
    print(f"{'='*65}\n")

    # ── REWRITE ───────────────────────────────────────────────────────────────
    print("🔄 [1/3] REWRITE\n")
    history = "USER: What is feature scaling?\nASSISTANT: Feature scaling normalizes input ranges..."
    followup = "Which algorithms need it?"
    msgs = [
        SystemMessage(content=REWRITE_SYSTEM),
        HumanMessage(content=f"History:\n{history}\n\nQuestion: {followup}"),
    ]
    t0 = time.perf_counter()
    r = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    rw = (r.content if isinstance(r.content, str) else str(r.content)).strip()
    print(f"   📥 '{followup}'\n   📤 '{rw}'\n   ⏱  {lat:.2f}s\n")
    time.sleep(1)

    # ── GRADING ───────────────────────────────────────────────────────────────
    print("🎯 [2/3] GRADING\n")
    cases = [
        (SAMPLE_CONTEXT[300:], "Which algorithms need feature scaling?", "yes"),
        ("The Eiffel Tower was built in 1889 for the World's Fair.", "Which algorithms need feature scaling?", "no"),
        (SAMPLE_CONTEXT[:300], "How does backpropagation work?", "yes"),
    ]

    correct = 0
    for doc, q, expected in cases:
        msgs = [
            SystemMessage(content=GRADE_SYSTEM),
            HumanMessage(content=f"Document:\n{doc[:400]}\nQuestion: {q}\nRelevant?"),
        ]
        t0 = time.perf_counter()
        r = llm.invoke(msgs)
        lat = time.perf_counter() - t0
        verdict = (r.content if isinstance(r.content, str) else str(r.content)).strip().lower()
        ok = verdict.startswith(expected)
        correct += int(ok)
        print(f"   {'✅' if ok else '❌'} '{verdict[:10]}' (attendu '{expected}') | {lat:.2f}s")
        time.sleep(1)

    print(f"\n   📊 Grading : {correct}/3\n")
    time.sleep(2)

    # ── GÉNÉRATION ────────────────────────────────────────────────────────────
    print("💬 [3/3] GÉNÉRATION\n")
    q = "Quels algorithmes nécessitent la normalisation des features et pourquoi ?"
    print(f"   ❓ {q}\n")
    msgs = [
        SystemMessage(content=RAG_SYSTEM),
        HumanMessage(content=f"Context:\n---\n{SAMPLE_CONTEXT}\n---\n\nQuestion: {q}\n\nAnswer:"),
    ]
    t0 = time.perf_counter()
    r = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    answer = r.content if isinstance(r.content, str) else str(r.content)

    print(f"   📝 ({len(answer)} chars, {lat:.2f}s):\n")
    print("   " + "\n   ".join(answer.strip().split("\n")[:10]))

    # Vérifications qualité — référence
    checks = {
        "Mentionne SVM ou Neural Network": any(k in answer for k in ["SVM", "neural", "réseau"]),
        "Mentionne tree-based": any(k in answer.lower() for k in ["tree", "arbre", "random forest", "xgboost"]),
        "Répond en français": any(k in answer for k in ["la ", "le ", "les ", "pour ", "les "]),
        "Longueur correcte (>100 chars)": len(answer) > 100,
    }

    print(f"\n   📊 Qualité :")
    total = 0
    for check, passed in checks.items():
        icon = "✅" if passed else "❌"
        print(f"      {icon} {check}")
        total += int(passed)

    print(f"\n{'='*65}")
    print(f"  📌 {MODEL} — Tests terminés (modèle de référence)")
    print(f"  📊 Grading: {correct}/3 | Qualité génération: {total}/4")
    print(f"  💡 Compare ces scores avec gemma-4-26b-it pour décider !")
    print(f"  🔄 Même config dans config.yaml — change model_name pour tester")
    print(f"{'='*65}\n")


def main():
    try:
        run_test()
    except KeyboardInterrupt:
        print("\n⛔ Interrompu.")
    except Exception as e:
        err = str(e)
        print(f"\n❌ Erreur : {err}")
        if "429" in err:
            print("⚠️  Quota dépassé.")


if __name__ == "__main__":
    main()
