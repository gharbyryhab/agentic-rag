"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  TEST — gemini-2.5-flash  +  gemini-3-flash-preview                          ║
║  Catégorie : LLM principal | RPD: 20 | RPM: 5                               ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  UTILITÉ POUR TON AGENTIC RAG :                                              ║
║  → MEILLEURE qualité Gemini — mais QUOTA TROP BAS pour dev/test              ║
║  → Réservé à la PRODUCTION ou démo finale                                    ║
║  → Ce script établit un PLAFOND DE QUALITÉ comme référence                  ║
║  → Compare tes résultats Gemma avec ce gold standard                         ║
║  ⚠️  ATTENTION : 20 RPD = 4 questions/jour (5 appels/question)               ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage :
    python -m scripts.test_gemini_flash
    python -m scripts.test_gemini_flash --model gemini-3-flash-preview
    python -m scripts.test_gemini_flash --gold-standard   # 1 seul appel, conserve le quota
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # ← parents[2] car on est 2 niveaux plus profondsys.path.insert(0, str(ROOT))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.config import get_settings

MODELS = {
    "gemini-2.5-flash": {"rpd": 20, "rpm": 5, "label": "Gold Standard Gemini (stable)"},
    "gemini-flash-latest": {"rpd": 20, "rpm": 5, "label": "Alias Flash Latest"},
    "gemini-3-flash-preview": {"rpd": 20, "rpm": 5, "label": "Gold Standard Gemini 3 (new gen)"},
}

# Contexte riche — test la capacité à comprendre un corpus technique dense
RICH_CONTEXT = """
[source: probabilistic_graphical_models.pdf | page: 34]
A Bayesian Network is a directed acyclic graph (DAG) where nodes represent random
variables and edges represent conditional dependencies. The joint distribution
factorizes as: P(X1,...,Xn) = ∏ P(Xi | Pa(Xi)) where Pa(Xi) are the parents of Xi.
Inference algorithms include Variable Elimination, Belief Propagation, and MCMC sampling.

[source: reinforcement_learning_sutton.pdf | page: 89]
The Bellman equation expresses the value function recursively:
V(s) = max_a [ R(s,a) + γ * Σ P(s'|s,a) * V(s') ]
where γ is the discount factor, R is the reward, and P is the transition probability.
Q-learning is a model-free algorithm that learns Q(s,a) values directly from experience.
The temporal difference (TD) error drives learning: δ = r + γV(s') - V(s).

[source: information_theory_cover.pdf | page: 15]
Shannon entropy measures uncertainty: H(X) = -Σ p(x) log p(x).
KL divergence measures the difference between distributions: D_KL(P||Q) = Σ p(x) log(p(x)/q(x)).
Mutual information measures dependence: I(X;Y) = H(X) - H(X|Y).
Cross-entropy loss used in ML is H(p,q) = -Σ p(x) log q(x).
"""

RAG_SYSTEM = """You are an expert assistant in data science, machine learning, and artificial intelligence.
Answer the user's question using ONLY the provided context.
CRITICAL: Always respond in the SAME language as the user's question.
Provide technically rigorous, well-structured answers. Cite formulas when relevant."""

GRADE_SYSTEM = """You are a grader assessing relevance of a retrieved document to a user question.
Output a single word: "yes" or "no"."""

REWRITE_SYSTEM = """Rewrite the question as a standalone query for vector search.
Keep the same language. Output only the rewritten question."""

# Question difficile — teste la compréhension de concepts avancés
HARD_QUESTION = (
    "Dans le contexte du reinforcement learning, explique la relation entre "
    "la TD error et l'équation de Bellman. Pourquoi la TD error est-elle le "
    "moteur de l'apprentissage dans Q-learning ?"
)


def run_gold_standard(model_name: str, api_key: str):
    """Un seul appel de génération — conserve le quota 20 RPD."""
    info = MODELS.get(model_name, {"rpd": "?", "label": "?"})

    print(f"\n{'='*65}")
    print(f"  🥇 GOLD STANDARD : {model_name}")
    print(f"  📊 RPD: {info['rpd']} | ⚠️  UTILISE AVEC PARCIMONIE")
    print(f"  🎯 {info['label']}")
    print(f"{'='*65}\n")

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.1,
        max_output_tokens=1500,
        top_p=0.95,
    )

    print(f"❓ Question : {HARD_QUESTION}\n")
    msgs = [
        SystemMessage(content=RAG_SYSTEM),
        HumanMessage(content=f"Context:\n---\n{RICH_CONTEXT}\n---\n\nQuestion: {HARD_QUESTION}\n\nAnswer:"),
    ]
    try:
        t0 = time.perf_counter()
        result = llm.invoke(msgs)
        lat = time.perf_counter() - t0
        answer = result.content if isinstance(result.content, str) else str(result.content)

        print(f"📝 Réponse Gold Standard ({len(answer)} chars, {lat:.2f}s) :\n")
        print("─" * 60)
        print(answer)
        print("─" * 60)

        # Vérifications qualité gold standard
        checks = {
            "Mentionne Bellman equation": "bellman" in answer.lower(),
            "Mentionne TD error": "td error" in answer.lower() or "temporal difference" in answer.lower(),
            "Mentionne Q-learning": "q-learning" in answer.lower() or "q learning" in answer.lower(),
            "Formule ou symboles mathématiques": any(c in answer for c in ["γ", "δ", "V(s", "Q(s"]),
            "Répond en français": any(k in answer for k in ["la ", "le ", "les ", "est ", "sont "]),
            "Longueur détaillée (>300 chars)": len(answer) > 300,
        }

        total = sum(checks.values())
        print(f"\n📊 Qualité gold standard :")
        for check, passed in checks.items():
            print(f"   {'✅' if passed else '❌'} {check}")

        print(f"\n🏆 Score : {total}/{len(checks)}")
        print(f"\n💡 Ce score est ta RÉFÉRENCE MAXIMALE.")
        print(f"   Compare les scores Gemma avec {total}/{len(checks)} pour évaluer le gap.")
        print(f"\n⚠️  Quota restant estimé : ~{info['rpd'] - 1} RPD")

    except Exception as e:
        err = str(e)
        print(f"❌ Erreur : {err}")
        if "429" in err and "PerDay" in err:
            print("⛔ Quota JOURNALIER épuisé — attends minuit UTC")
        elif "429" in err:
            print("⚠️  Rate limit par minute — attends 60s")


def run_full_test(model_name: str, api_key: str):
    """Tests complets — utilise ~4 appels sur les 20 RPD."""
    info = MODELS.get(model_name, {"rpd": "?", "label": "?"})

    print(f"\n{'='*65}")
    print(f"  🥇 TEST COMPLET : {model_name}")
    print(f"  ⚠️  CE TEST UTILISE ~4 APPELS SUR {info['rpd']} RPD DISPONIBLES")
    print(f"{'='*65}\n")

    input("  Appuie sur ENTER pour confirmer... (Ctrl+C pour annuler)\n")

    llm = ChatGoogleGenerativeAI(
        model=model_name,
        google_api_key=api_key,
        temperature=0.1,
        max_output_tokens=1000,
        top_p=0.95,
    )

    # Rewrite
    print("🔄 [1/3] REWRITE\n")
    history = "USER: What is KL divergence?\nASSISTANT: KL divergence measures..."
    msgs = [
        SystemMessage(content=REWRITE_SYSTEM),
        HumanMessage(content=f"History:\n{history}\n\nQuestion: How is it used in VAEs?"),
    ]
    t0 = time.perf_counter()
    r = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    rw = (r.content if isinstance(r.content, str) else str(r.content)).strip()
    print(f"   📤 '{rw}' | {lat:.2f}s\n")
    time.sleep(3)

    # Grading
    print("🎯 [2/3] GRADING\n")
    msgs = [
        SystemMessage(content=GRADE_SYSTEM),
        HumanMessage(content=f"Document:\n{RICH_CONTEXT[800:]}\nQuestion: Explain KL divergence\nRelevant?"),
    ]
    t0 = time.perf_counter()
    r = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    verdict = (r.content if isinstance(r.content, str) else str(r.content)).strip()
    print(f"   → '{verdict[:20]}' | {lat:.2f}s\n")
    time.sleep(3)

    # Génération
    print("💬 [3/3] GÉNÉRATION (question difficile)\n")
    msgs = [
        SystemMessage(content=RAG_SYSTEM),
        HumanMessage(content=f"Context:\n---\n{RICH_CONTEXT}\n---\n\nQuestion: {HARD_QUESTION}\n\nAnswer:"),
    ]
    t0 = time.perf_counter()
    r = llm.invoke(msgs)
    lat = time.perf_counter() - t0
    answer = r.content if isinstance(r.content, str) else str(r.content)

    print(f"   📝 ({len(answer)} chars, {lat:.2f}s):\n")
    print("   " + "\n   ".join(answer.strip().split("\n")[:15]))

    print(f"\n{'='*65}")
    print(f"  🥇 Gold standard établi pour : {model_name}")
    print(f"  📋 Utilise ces réponses comme RÉFÉRENCE pour évaluer Gemma 4")
    print(f"{'='*65}\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="gemini-2.5-flash", choices=list(MODELS.keys()))
    parser.add_argument("--gold-standard", action="store_true",
                        help="1 seul appel (conserve quota) — juste la génération")
    args = parser.parse_args()

    cfg = get_settings()
    if not cfg.gemini_api_key:
        print("❌ GEMINI_API_KEY manquant dans .env")
        sys.exit(1)

    try:
        if args.gold_standard:
            run_gold_standard(args.model, cfg.gemini_api_key)
        else:
            run_full_test(args.model, cfg.gemini_api_key)
    except KeyboardInterrupt:
        print("\n⛔ Annulé — quota préservé.")
    except Exception as e:
        err = str(e)
        print(f"\n❌ Erreur : {err}")
        if "429" in err and "PerDay" in err:
            print("⛔ Quota JOURNALIER épuisé.")


if __name__ == "__main__":
    main()
