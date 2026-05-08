"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  TEST — gemma-4-26b-it                                                       ║
║  Catégorie : LLM local (Gemma 4) | RPD: 1 500 | RPM: 15                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  UTILITÉ POUR TON AGENTIC RAG :                                              ║
║  → Modèle recommandé pour développement et amélioration du RAG               ║
║  → Raisonnement avancé + contexte 256K tokens                                ║
║  → Pipeline complet : rewrite + grade + generate                             ║
║  → 1 500 RPD = ~300 questions/jour avec 5 appels LLM par question            ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage :
    python -m scripts.test_gemma4_26b
    python -m scripts.test_gemma4_26b "Explain overfitting and regularization"
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # ← parents[2] car on est 2 niveaux plus profond
sys.path.insert(0, str(ROOT))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings

MODEL = "gemma-4-26b-a4b-it"
RPD = 1_500
RPM = 15

# ── Contexte de test représentatif de tes 101 books ──────────────────────────
SAMPLE_CONTEXT = """
[source: hands_on_machine_learning.pdf | page: 142]
Regularization techniques help prevent overfitting by constraining the model.
L1 regularization (Lasso) adds the sum of absolute values of weights to the loss,
encouraging sparsity. L2 regularization (Ridge) adds the sum of squared weights,
shrinking them toward zero without making them exactly zero.
Dropout randomly sets a fraction of neurons to zero during training.

[source: deep_learning_book.pdf | page: 228]
Early stopping monitors validation loss and stops training when it starts increasing,
even if training loss continues to decrease. This is a form of implicit regularization.
Batch normalization also has a slight regularizing effect.
"""

RAG_SYSTEM = """You are an expert assistant in data science, machine learning, and artificial intelligence.
Answer the user's question using ONLY the provided context.
CRITICAL: Always respond in the SAME language as the user's question.
If the context is insufficient, say so explicitly. Do not invent.
Prefer concise, precise, technical answers. When code is relevant, provide minimal runnable snippets."""

GRADE_SYSTEM = """You are a grader assessing relevance of a retrieved document to a user question.
If the document contains keywords or semantic meaning related to the question, grade it as relevant.
Output a single word: "yes" or "no"."""

REWRITE_SYSTEM = """Given the conversation history and the new user question, rewrite the question into
a standalone, self-contained query suitable for vector search.
Keep EXACTLY the same language as the original question.
Output only the rewritten question, nothing else."""


def run_test(custom_question: str | None = None):
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
    print(f"  📊  RPD: {RPD} | RPM: {RPM}")
    print(f"  🎯  Profil : Raisonnement avancé Gemma 4, 256K ctx")
    print(f"{'='*65}\n")

    # ── TEST 1 : REWRITE (reformulation contextuelle) ─────────────────────────
    print("🔄 [1/3] TEST REWRITE — reformulation de question avec historique\n")
    print("   Cas d'usage : L'utilisateur pose une question vague après un échange.")
    print("   Le modèle doit créer une query standalone pour la recherche vectorielle.\n")

    history = "USER: What is overfitting?\nASSISTANT: Overfitting occurs when a model..."
    followup = "And how do we fix it?"

    rewrite_user = f"Conversation history:\n{history}\n\nNew question: {followup}"
    msgs = [SystemMessage(content=REWRITE_SYSTEM), HumanMessage(content=rewrite_user)]
    t0 = time.perf_counter()
    result = llm.invoke(msgs)
    lat = time.perf_counter() - t0

    rewritten = result.content if isinstance(result.content, str) else str(result.content)
    print(f"   📥 Question originale : '{followup}'")
    print(f"   📤 Question reformulée : '{rewritten.strip()}'")
    print(f"   ⏱  Latence : {lat:.2f}s")
    standalone = len(rewritten) > 20 and "?" in rewritten
    print(f"   ✅ Standalone : {'Oui' if standalone else '⚠️ Vérifier'}\n")

    time.sleep(2)

    # ── TEST 2 : GRADING ─────────────────────────────────────────────────────
    print("🎯 [2/3] TEST GRADING — évaluation pertinence des chunks\n")
    print("   Cas d'usage : Filtrer les chunks non pertinents AVANT la génération.")
    print("   Le modèle doit répondre uniquement 'yes' ou 'no'.\n")

    grade_cases = [
        ("PERTINENT", SAMPLE_CONTEXT[:300], "How do L1 and L2 regularization differ?", "yes"),
        ("NON PERTINENT", "The history of Python dates back to 1991 when Guido van Rossum...", "How do L1 and L2 regularization differ?", "no"),
    ]

    grade_correct = 0
    for label, doc, q, expected in grade_cases:
        grade_user = f"Document:\n{doc}\n\nQuestion: {q}\n\nIs this document relevant?"
        msgs = [SystemMessage(content=GRADE_SYSTEM), HumanMessage(content=grade_user)]
        t0 = time.perf_counter()
        result = llm.invoke(msgs)
        lat = time.perf_counter() - t0
        verdict = (result.content if isinstance(result.content, str) else str(result.content)).strip().lower()
        correct = verdict.startswith(expected)
        grade_correct += int(correct)
        icon = "✅" if correct else "❌"
        print(f"   {icon} [{label}] Réponse: '{verdict[:20]}' | Attendu: '{expected}' | {lat:.2f}s")
        time.sleep(1)

    print(f"\n   📊 Score grading : {grade_correct}/2\n")
    time.sleep(2)

    # ── TEST 3 : GÉNÉRATION ───────────────────────────────────────────────────
    print("💬 [3/3] TEST GÉNÉRATION — réponse technique avec contexte RAG\n")
    question = custom_question or "Explique les techniques de régularisation pour éviter l'overfitting. Donne des exemples concrets."
    print(f"   ❓ Question : {question}\n")

    rag_user = f"Context:\n---\n{SAMPLE_CONTEXT}\n---\n\nQuestion: {question}\n\nAnswer:"
    msgs = [SystemMessage(content=RAG_SYSTEM), HumanMessage(content=rag_user)]
    t0 = time.perf_counter()
    result = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    answer = result.content if isinstance(result.content, str) else str(result.content)

    print(f"   📝 Réponse ({len(answer)} chars, {lat:.2f}s) :\n")
    print("   " + "\n   ".join(answer.strip().split("\n")))

    # Vérifications qualité
    checks = {
        "L1/L2 mentionné": any(k in answer for k in ["L1", "L2", "Lasso", "Ridge"]),
        "Dropout mentionné": "Dropout" in answer or "dropout" in answer,
        "Early stopping mentionné": "early stopping" in answer.lower() or "arrêt" in answer.lower(),
        "Répond en français": any(k in answer for k in ["la", "le", "les", "pour", "des", "est"]),
    }

    print(f"\n   📊 Vérifications qualité :")
    total = 0
    for check, passed in checks.items():
        icon = "✅" if passed else "❌"
        print(f"      {icon} {check}")
        total += int(passed)
    print(f"\n   🏆 Score qualité : {total}/{len(checks)}")

    print(f"\n{'='*65}")
    print(f"  ✅ {MODEL} — Tests terminés")
    print(f"  💡 À utiliser pour : génération + rewrite + grading complet")
    print(f"  📊 Budget : ~{RPD // 5} questions/jour (5 appels/question)")
    print(f"{'='*65}\n")


def main():
    custom = " ".join(sys.argv[1:]) or None
    try:
        run_test(custom)
    except KeyboardInterrupt:
        print("\n⛔ Interrompu.")
    except Exception as e:
        err = str(e)
        print(f"\n❌ Erreur : {err}")
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            print("⚠️  Quota dépassé — attends ou utilise un autre modèle.")
        elif "404" in err:
            print("⚠️  Modèle introuvable. Vérifie le nom dans l'API Gemini.")


if __name__ == "__main__":
    main()
