"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  TEST — gemma-4-31b-it                                                       ║
║  Catégorie : LLM local (Gemma 4) | RPD: 1 500 | RPM: 15                     ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  UTILITÉ POUR TON AGENTIC RAG :                                              ║
║  → MEILLEURE qualité Gemma 4 — supérieur à 26B en raisonnement complexe      ║
║  → Idéal pour des questions ML/AI avancées (papers, mathématiques)           ║
║  → Test spécifique : raisonnement multi-étapes sur ML                        ║
║  → Même quota que 26B (1 500 RPD) — choisir selon la qualité mesurée        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage :
    python -m scripts.test_gemma4_31b
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

MODEL = "gemma-4-31b-it"
RPD = 1_500
RPM = 15

# Contexte plus complexe — test de raisonnement avancé (domaine ML)
COMPLEX_CONTEXT = """
[source: attention_is_all_you_need.pdf | page: 3]
The Transformer model relies entirely on attention mechanisms, dispensing with recurrence
and convolutions. The attention function maps a query and a set of key-value pairs to an
output. The output is a weighted sum of the values, where the weight assigned to each value
is computed by a compatibility function of the query with the corresponding key.

Multi-Head Attention allows the model to jointly attend to information from different
representation subspaces at different positions. With a single attention head, averaging
inhibits this capability.

[source: bert_paper.pdf | page: 2]
BERT (Bidirectional Encoder Representations from Transformers) pre-trains deep bidirectional
representations from unlabeled text by jointly conditioning on both left and right context.
BERT uses masked language modeling (MLM) as a pre-training objective: randomly masking 15%
of tokens and predicting them. It also uses Next Sentence Prediction (NSP).

[source: illustrated_transformer_blog.pdf | page: 1]
Positional encoding is added to the input embeddings to give the model information about
the position of words in the sequence. The authors use sine and cosine functions of
different frequencies. This allows the model to generalize to sequence lengths not seen
during training.
"""

RAG_SYSTEM = """You are an expert assistant in data science, machine learning, and artificial intelligence.
Answer the user's question using ONLY the provided context.
CRITICAL: Always respond in the SAME language as the user's question.
If the context is insufficient, say so explicitly. Do not invent.
Prefer detailed, technically rigorous answers for advanced ML topics."""

GRADE_SYSTEM = """You are a grader assessing relevance of a retrieved document to a user question.
If the document contains keywords or semantic meaning related to the question, grade it as relevant.
Output a single word: "yes" or "no"."""

REWRITE_SYSTEM = """Given the conversation history and the new user question, rewrite the question into
a standalone, self-contained query suitable for vector search.
Keep EXACTLY the same language as the original question.
Output only the rewritten question, nothing else."""

# ── Test de raisonnement multi-étapes (spécifique 31B) ───────────────────────
REASONING_SYSTEM = """You are an expert ML researcher. Analyze the given concept step by step.
Be technically precise and cite specific components when relevant."""


def run_test():
    cfg = get_settings()
    if not cfg.gemini_api_key:
        print("❌ GEMINI_API_KEY manquant dans .env")
        sys.exit(1)

    llm = ChatGoogleGenerativeAI(
        model=MODEL,
        google_api_key=cfg.gemini_api_key,
        temperature=0.15,  # légèrement plus bas pour la précision technique
        max_output_tokens=1500,
        top_p=0.92,
    )

    print(f"\n{'='*65}")
    print(f"  🤖  TEST MODÈLE : {MODEL}")
    print(f"  📊  RPD: {RPD} | RPM: {RPM}")
    print(f"  🎯  Profil : Meilleur raisonnement Gemma, 256K ctx")
    print(f"{'='*65}\n")

    # ── TEST 1 : REWRITE complexe (référence à un concept antérieur) ──────────
    print("🔄 [1/4] TEST REWRITE — question avec référence croisée\n")
    print("   Objectif : Le 31B doit résoudre une référence pronominale complexe.\n")

    history = (
        "USER: Comment fonctionne le mécanisme d'attention dans les Transformers ?\n"
        "ASSISTANT: L'attention calcule une somme pondérée des valeurs...\n"
        "USER: Quelle est la différence avec la version multi-tête ?\n"
        "ASSISTANT: Multi-Head Attention projette les requêtes dans plusieurs sous-espaces..."
    )
    followup = "Et pourquoi c'est mieux que l'ancienne approche ?"

    rewrite_user = f"Conversation history:\n{history}\n\nNew question: {followup}"
    msgs = [SystemMessage(content=REWRITE_SYSTEM), HumanMessage(content=rewrite_user)]
    t0 = time.perf_counter()
    result = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    rewritten = (result.content if isinstance(result.content, str) else str(result.content)).strip()

    print(f"   📥 Question : '{followup}'")
    print(f"   📤 Reformulée : '{rewritten}'")
    print(f"   ⏱  {lat:.2f}s")
    mentions_mha = any(k in rewritten.lower() for k in ["multi-head", "multi-tête", "attention", "transformer"])
    print(f"   ✅ Résout la référence : {'Oui' if mentions_mha else '⚠️ Partiel'}\n")

    time.sleep(2)

    # ── TEST 2 : GRADING sur papiers académiques ──────────────────────────────
    print("🎯 [2/4] TEST GRADING — chunks de papers ML\n")
    print("   Objectif : Évaluer la précision sur des textes académiques denses.\n")

    grade_cases = [
        ("Positional Encoding → Transformers", COMPLEX_CONTEXT[1100:], "How does Transformer encode position?", "yes"),
        ("BERT MLM → Gradient Descent", COMPLEX_CONTEXT[650:1100], "Explain stochastic gradient descent variants", "no"),
        ("Multi-Head Attention → MHA", COMPLEX_CONTEXT[:600], "What is multi-head attention?", "yes"),
    ]

    grade_correct = 0
    for label, doc, q, expected in grade_cases:
        grade_user = f"Document:\n{doc[:500]}\n\nQuestion: {q}\n\nIs this document relevant?"
        msgs = [SystemMessage(content=GRADE_SYSTEM), HumanMessage(content=grade_user)]
        t0 = time.perf_counter()
        result = llm.invoke(msgs)
        lat = time.perf_counter() - t0
        verdict = (result.content if isinstance(result.content, str) else str(result.content)).strip().lower()
        correct = verdict.startswith(expected)
        grade_correct += int(correct)
        icon = "✅" if correct else "❌"
        print(f"   {icon} [{label}] → '{verdict[:15]}' (attendu: '{expected}') | {lat:.2f}s")
        time.sleep(1)

    print(f"\n   📊 Score grading : {grade_correct}/3\n")
    time.sleep(2)

    # ── TEST 3 : GÉNÉRATION sur topic avancé (Transformers) ──────────────────
    print("💬 [3/4] TEST GÉNÉRATION — question avancée Transformers\n")
    question = "Compare l'attention multi-tête (MHA) avec l'attention simple. Pourquoi MHA est-il supérieur pour capter des représentations complexes ?"
    print(f"   ❓ Question : {question}\n")

    rag_user = f"Context:\n---\n{COMPLEX_CONTEXT}\n---\n\nQuestion: {question}\n\nAnswer:"
    msgs = [SystemMessage(content=RAG_SYSTEM), HumanMessage(content=rag_user)]
    t0 = time.perf_counter()
    result = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    answer = result.content if isinstance(result.content, str) else str(result.content)

    print(f"   📝 Réponse ({len(answer)} chars, {lat:.2f}s) :\n")
    print("   " + "\n   ".join(answer.strip().split("\n")[:15]))
    if len(answer.split("\n")) > 15:
        print("   [...]")

    time.sleep(2)

    # ── TEST 4 : RAISONNEMENT MULTI-ÉTAPES (spécifique 31B) ──────────────────
    print("\n🧠 [4/4] TEST RAISONNEMENT — analyse step-by-step (bonus 31B)\n")
    print("   Objectif : Tester la capacité de raisonnement avancé unique au 31B.\n")

    reasoning_q = (
        "Given that BERT uses bidirectional attention and the original Transformer uses "
        "causal (unidirectional) attention in the decoder, explain step by step why "
        "BERT cannot be used directly as an autoregressive text generator."
    )
    msgs = [
        SystemMessage(content=REASONING_SYSTEM),
        HumanMessage(content=reasoning_q),
    ]
    t0 = time.perf_counter()
    result = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    reasoning = result.content if isinstance(result.content, str) else str(result.content)

    steps = [l for l in reasoning.split("\n") if l.strip()]
    print(f"   📝 Raisonnement ({len(steps)} lignes, {lat:.2f}s) :\n")
    for line in steps[:12]:
        print(f"   {line}")
    if len(steps) > 12:
        print(f"   [...] ({len(steps) - 12} lignes supplémentaires)")

    # Score global
    gen_checks = {
        "MHA vs Single Head expliqué": any(k in answer for k in ["subspace", "sous-espace", "jointly", "conjointement"]),
        "Répond en français": any(k in answer for k in ["la ", "le ", "les ", "est ", "sont "]),
        "Longueur suffisante": len(answer) > 200,
        "BERT raisonnement step-by-step": "step" in reasoning.lower() or "étape" in reasoning.lower() or any(c.isdigit() for c in reasoning[:100]),
    }

    print(f"\n   📊 Vérifications qualité :")
    total = 0
    for check, passed in gen_checks.items():
        icon = "✅" if passed else "❌"
        print(f"      {icon} {check}")
        total += int(passed)

    print(f"\n{'='*65}")
    print(f"  🥇 {MODEL} — Tests terminés")
    print(f"  📊 Score : {total}/4 + grading {grade_correct}/3")
    print(f"  💡 Recommandé pour : RAG sur papers ML, questions complexes")
    print(f"  ⚖️  vs 26B : meilleure qualité, même quota — tester les 2 !")
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
        elif "404" in err:
            print("⚠️  Modèle introuvable.")


if __name__ == "__main__":
    main()
