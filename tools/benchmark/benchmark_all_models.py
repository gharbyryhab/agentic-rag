"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           BENCHMARK COMPLET — TOUS LES MODÈLES GEMINI / GEMMA               ║
║                  Agentic RAG — ML / Data Science / AI                        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Ce script teste TOUS les modèles disponibles avec ta clé API Gemini AI Studio.
Il mesure 4 dimensions critiques pour ton Agentic RAG :
  1. REWRITE   — reformuler une question avec historique de conversation
  2. GRADING   — évaluer si un chunk est pertinent (yes/no)
  3. GENERATION — générer une réponse technique à partir de contexte
  4. QUOTA     — détecter les erreurs 429 (limite dépassée)

Usage :
    python -m scripts.benchmark_all_models
    python -m scripts.benchmark_all_models --models gemma-4-26b-it gemma-3-27b-it
    python -m scripts.benchmark_all_models --output results/benchmark.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]  # ← parents[2] car on est 2 niveaux plus profondsys.path.insert(0, str(ROOT))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from src.config import get_settings

# ──────────────────────────────────────────────────────────────────────────────
# TOUS LES MODÈLES DISPONIBLES — avec leur profil d'utilisation
# ──────────────────────────────────────────────────────────────────────────────
ALL_MODELS = {
    # ── LLMs principaux (Gemini) ──────────────────────────────────────────────
    "gemini-2.5-flash": {
        "category": "LLM principal",
        "rpd": 20,
        "rpm": 5,
        "profile": "Meilleure qualité Gemini, mais quota trop bas pour dev/test",
        "recommended_for": ["génération finale haute qualité"],
        "warning": "⚠️  Quota 20 RPD — réservé à la PRODUCTION uniquement",
    },
    "gemini-3-flash-preview": {
        "category": "LLM principal",
        "rpd": 20,
        "rpm": 5,
        "profile": "Nouvelle génération rapide, contexte 1M tokens",
        "recommended_for": ["génération finale haute qualité"],
        "warning": "⚠️  Quota 20 RPD — réservé à la PRODUCTION uniquement",
    },
    "gemini-flash-latest": {
        "category": "LLM principal (alias)",
        "rpd": 20,
        "rpm": 5,
        "profile": "Alias du modèle Flash le plus récent",
        "recommended_for": ["génération finale"],
        "warning": "⚠️  Quota 20 RPD",
    },
    # ── LLMs légers (Gemini Lite) ──────────────────────────────────────────────
    "gemini-3.1-flash-lite-preview": {
        "category": "LLM léger",
        "rpd": 500,
        "rpm": 15,
        "profile": "Ultra économique, volume élevé — parfait pour le GRADING",
        "recommended_for": ["grading chunks", "pré-filtrage", "rewrite simple"],
        "warning": "✅ Bon compromis qualité/quota pour tâches répétitives",
    },
    "gemini-2.5-flash-lite": {
        "category": "LLM léger",
        "rpd": 20,
        "rpm": 30,
        "profile": "Ultra rapide, latence minimale — mais quota journalier limité",
        "recommended_for": ["grading", "tâches simples"],
        "warning": "⚠️  Quota 20 RPD malgré RPM élevé",
    },
    # ── Open-weights Gemma 4 ──────────────────────────────────────────────────
    "gemma-4-26b-it": {
        "category": "LLM local (Gemma 4)",
        "rpd": 1500,
        "rpm": 15,
        "profile": "Raisonnement avancé, 256K ctx — MEILLEUR rapport qualité/quota",
        "recommended_for": ["génération", "rewrite", "grading", "RAG complet"],
        "warning": "🏆 RECOMMANDÉ pour développement et amélioration du RAG",
    },
    "gemma-4-31b-it": {
        "category": "LLM local (Gemma 4)",
        "rpd": 1500,
        "rpm": 15,
        "profile": "Meilleur raisonnement Gemma, 256K ctx, nécessite 1 GPU 80GB si local",
        "recommended_for": ["génération haute qualité", "RAG complexe"],
        "warning": "🥇 Meilleure qualité Gemma, même quota que 26B",
    },
    # ── Open-weights Gemma 3 ──────────────────────────────────────────────────
    "gemma-3-27b-it": {
        "category": "LLM local léger (Gemma 3)",
        "rpd": 14400,
        "rpm": 30,
        "profile": "Modèle modéré, 128K ctx — MEILLEUR VOLUME pour tests intensifs",
        "recommended_for": ["tests massifs", "itération rapide", "benchmarking"],
        "warning": "🚀 14 400 RPD = ~2 880 questions/jour (5 appels/question)",
    },
    "gemma-3-12b-it": {
        "category": "LLM local léger (Gemma 3)",
        "rpd": 14400,
        "rpm": 30,
        "profile": "Modèle moyen, 128K ctx — celui actuellement dans ton config.yaml",
        "recommended_for": ["dev quotidien", "tests rapides"],
        "warning": "📌 Ton modèle actuel — correct mais inférieur à Gemma 4 en qualité",
    },
    "gemma-3-4b-it": {
        "category": "LLM local léger (Gemma 3)",
        "rpd": 14400,
        "rpm": 20,
        "profile": "Léger, tâches simples — trop faible pour RAG ML technique",
        "recommended_for": ["pré-filtrage ultra simple", "classification basique"],
        "warning": "❌ Déconseillé pour génération RAG sur ML/AI technique",
    },
    "gemma-3-1b-it": {
        "category": "LLM local léger (Gemma 3)",
        "rpd": 14400,
        "rpm": 30,
        "profile": "Très léger, edge/mobile — pour tâches triviales uniquement",
        "recommended_for": ["classification yes/no très simple"],
        "warning": "❌ Trop faible pour du RAG sur contenu technique",
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# QUESTIONS DE TEST — représentatives de ton corpus ML/DS/AI
# ──────────────────────────────────────────────────────────────────────────────
TEST_REWRITE = {
    "history": "USER: Qu'est-ce que le gradient descent ?\nASSISTANT: C'est un algorithme d'optimisation...",
    "question": "Et ses variantes ?",
    "system": (
        "Given the conversation history and the new user question, rewrite the question into "
        "a standalone, self-contained query suitable for vector search. "
        "Keep EXACTLY the same language as the original question. "
        "Output only the rewritten question, nothing else."
    ),
    "expected_contains": ["gradient", "variantes", "SGD", "Adam", "momentum"],
}

TEST_GRADE = {
    "document": (
        "Stochastic Gradient Descent (SGD) is a variant of gradient descent where "
        "we update the model parameters using only one sample at a time. "
        "Mini-batch SGD uses a small batch of samples. Adam optimizer combines "
        "momentum and RMSprop for adaptive learning rates."
    ),
    "question": "What are the variants of gradient descent?",
    "system": (
        "You are a grader assessing relevance of a retrieved document to a user question. "
        "If the document contains keywords or semantic meaning related to the question, "
        "grade it as relevant. Output a single word: \"yes\" or \"no\"."
    ),
    "expected": "yes",
}

TEST_GRADE_IRRELEVANT = {
    "document": (
        "The Python programming language was created by Guido van Rossum in 1991. "
        "Python is known for its simple and readable syntax. It is widely used in "
        "web development, automation and scripting tasks."
    ),
    "question": "What are the variants of gradient descent?",
    "system": (
        "You are a grader assessing relevance of a retrieved document to a user question. "
        "If the document contains keywords or semantic meaning related to the question, "
        "grade it as relevant. Output a single word: \"yes\" or \"no\"."
    ),
    "expected": "no",
}

TEST_GENERATION = {
    "context": """
[source: deep_learning_book.pdf]
Backpropagation is an algorithm for computing gradients in neural networks.
It works by applying the chain rule of calculus repeatedly to compute the gradient
of the loss with respect to each parameter. The algorithm has two passes:
forward pass (compute activations) and backward pass (compute gradients).

[source: hands_on_ml.pdf]
The vanishing gradient problem occurs when gradients become very small as they
propagate through many layers. Solutions include: ReLU activations, batch normalization,
residual connections (ResNets), and careful weight initialization (Xavier/He init).
""",
    "question": "Comment fonctionne la rétropropagation et quel est le problème des gradients qui disparaissent ?",
    "system": (
        "You are an expert assistant in data science, machine learning, and artificial intelligence. "
        "Answer the user's question using ONLY the provided context. "
        "CRITICAL: Always respond in the SAME language as the user's question. "
        "If the question is in French, answer in French. "
        "If the context is insufficient, say so explicitly. Do not invent. "
        "Prefer concise, precise, technical answers."
    ),
    "quality_checks": {
        "mentions_chain_rule": ["chain rule", "règle de la chaîne", "dérivée"],
        "mentions_vanishing": ["vanishing", "disparaissent", "évanouissement", "gradient"],
        "mentions_solutions": ["ReLU", "batch norm", "ResNet", "Xavier", "He"],
        "answers_in_french": ["la", "le", "les", "est", "sont", "de", "du"],
    },
}


# ──────────────────────────────────────────────────────────────────────────────
# RUNNER
# ──────────────────────────────────────────────────────────────────────────────
def call_model(model_name: str, api_key: str, system: str, user: str) -> tuple[str, float, str | None]:
    """
    Appelle un modèle et retourne (réponse, latence_secondes, erreur_ou_None).
    """
    try:
        llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
            temperature=0.2,
            max_output_tokens=512,
            top_p=0.95,
            convert_system_message_to_human=False,
        )
        msgs = [SystemMessage(content=system), HumanMessage(content=user)]
        t0 = time.perf_counter()
        result = llm.invoke(msgs)
        latency = time.perf_counter() - t0
        content = result.content if isinstance(result.content, str) else str(result.content)
        return content.strip(), latency, None
    except Exception as e:
        err = str(e)
        return "", 0.0, err


def classify_error(err: str) -> str:
    if not err:
        return "OK"
    if "429" in err or "RESOURCE_EXHAUSTED" in err:
        if "PerDay" in err:
            return "QUOTA_DAY"
        return "QUOTA_MINUTE"
    if "404" in err or "not found" in err.lower():
        return "MODEL_NOT_FOUND"
    if "API_KEY" in err or "invalid" in err.lower() and "key" in err.lower():
        return "API_KEY_INVALID"
    return "ERROR"


def score_rewrite(response: str) -> dict:
    resp_lower = response.lower()
    hits = [kw for kw in TEST_REWRITE["expected_contains"] if kw.lower() in resp_lower]
    standalone = len(response) > 20 and "?" in response
    return {
        "standalone_question": standalone,
        "keyword_hits": hits,
        "score": int(standalone) + len(hits),
    }


def score_grade(response: str, expected: str) -> dict:
    resp_lower = response.lower().strip()
    correct = resp_lower.startswith(expected)
    concise = len(response) <= 10
    return {
        "correct": correct,
        "concise_output": concise,
        "raw_output": response[:50],
        "score": 2 if (correct and concise) else (1 if correct else 0),
    }


def score_generation(response: str) -> dict:
    resp_lower = response.lower()
    checks = {}
    total = 0
    for check_name, keywords in TEST_GENERATION["quality_checks"].items():
        hit = any(kw.lower() in resp_lower for kw in keywords)
        checks[check_name] = hit
        total += int(hit)
    return {
        "checks": checks,
        "total_score": total,
        "response_length": len(response),
        "score": total,
    }


def test_model(model_name: str, api_key: str) -> dict[str, Any]:
    info = ALL_MODELS.get(model_name, {"category": "inconnu", "rpd": "?", "rpm": "?"})
    result: dict[str, Any] = {
        "model": model_name,
        "category": info.get("category", "?"),
        "rpd": info.get("rpd", "?"),
        "profile": info.get("profile", "?"),
        "warning": info.get("warning", ""),
        "tests": {},
        "overall_score": 0,
        "max_score": 0,
        "status": "OK",
    }

    # ── TEST 1 : REWRITE ──────────────────────────────────────────────────────
    print(f"    [1/3] Rewrite... ", end="", flush=True)
    user_rewrite = (
        f"Conversation history:\n{TEST_REWRITE['history']}\n\n"
        f"New question: {TEST_REWRITE['question']}"
    )
    resp, lat, err = call_model(model_name, api_key, TEST_REWRITE["system"], user_rewrite)
    err_type = classify_error(err)

    if err_type == "QUOTA_DAY":
        result["status"] = "QUOTA_DAY"
        result["tests"]["rewrite"] = {"status": "QUOTA_DAY", "latency": 0}
        print("⛔ QUOTA JOURNALIER ÉPUISÉ")
        return result
    elif err_type == "MODEL_NOT_FOUND":
        result["status"] = "MODEL_NOT_FOUND"
        result["tests"]["rewrite"] = {"status": "NOT_FOUND", "latency": 0}
        print("❌ MODÈLE INTROUVABLE")
        return result
    elif err:
        result["tests"]["rewrite"] = {"status": err_type, "error": err[:100], "latency": 0}
        print(f"❌ {err_type}")
    else:
        scores = score_rewrite(resp)
        result["tests"]["rewrite"] = {
            "status": "OK",
            "response": resp[:200],
            "latency_s": round(lat, 2),
            **scores,
        }
        result["overall_score"] += scores["score"]
        result["max_score"] += 6
        print(f"✅ {lat:.1f}s | score {scores['score']}/6")

    time.sleep(1)  # éviter rate limit par minute

    # ── TEST 2a : GRADE (pertinent) ───────────────────────────────────────────
    print(f"    [2/3] Grade (pertinent)... ", end="", flush=True)
    user_grade = f"Document:\n{TEST_GRADE['document']}\n\nQuestion: {TEST_GRADE['question']}\n\nIs this document relevant?"
    resp, lat, err = call_model(model_name, api_key, TEST_GRADE["system"], user_grade)
    err_type = classify_error(err)

    if err:
        result["tests"]["grade_relevant"] = {"status": err_type, "error": err[:100]}
        print(f"❌ {err_type}")
    else:
        scores = score_grade(resp, "yes")
        result["tests"]["grade_relevant"] = {
            "status": "OK",
            "latency_s": round(lat, 2),
            **scores,
        }
        result["overall_score"] += scores["score"]
        result["max_score"] += 2
        ok = "✅" if scores["correct"] else "❌"
        print(f"{ok} '{resp[:20]}' | {lat:.1f}s | score {scores['score']}/2")

    time.sleep(1)

    # ── TEST 2b : GRADE (non pertinent) ──────────────────────────────────────
    print(f"    [2b/3] Grade (non pertinent)... ", end="", flush=True)
    user_grade_irr = (
        f"Document:\n{TEST_GRADE_IRRELEVANT['document']}\n\n"
        f"Question: {TEST_GRADE_IRRELEVANT['question']}\n\nIs this document relevant?"
    )
    resp, lat, err = call_model(model_name, api_key, TEST_GRADE_IRRELEVANT["system"], user_grade_irr)
    err_type = classify_error(err)

    if err:
        result["tests"]["grade_irrelevant"] = {"status": err_type, "error": err[:100]}
        print(f"❌ {err_type}")
    else:
        scores = score_grade(resp, "no")
        result["tests"]["grade_irrelevant"] = {
            "status": "OK",
            "latency_s": round(lat, 2),
            **scores,
        }
        result["overall_score"] += scores["score"]
        result["max_score"] += 2
        ok = "✅" if scores["correct"] else "❌"
        print(f"{ok} '{resp[:20]}' | {lat:.1f}s | score {scores['score']}/2")

    time.sleep(2)

    # ── TEST 3 : GENERATION ───────────────────────────────────────────────────
    print(f"    [3/3] Génération (réponse technique)... ", end="", flush=True)
    user_gen = (
        f"Context:\n---\n{TEST_GENERATION['context']}\n---\n\n"
        f"Question: {TEST_GENERATION['question']}\n\nAnswer (in the same language as the question):"
    )
    resp, lat, err = call_model(model_name, api_key, TEST_GENERATION["system"], user_gen)
    err_type = classify_error(err)

    if err:
        result["tests"]["generation"] = {"status": err_type, "error": err[:100]}
        print(f"❌ {err_type}")
    else:
        scores = score_generation(resp)
        result["tests"]["generation"] = {
            "status": "OK",
            "response_preview": resp[:300],
            "latency_s": round(lat, 2),
            **scores,
        }
        result["overall_score"] += scores["score"]
        result["max_score"] += 4
        print(f"✅ {lat:.1f}s | score {scores['score']}/4 | {len(resp)} chars")

    return result


# ──────────────────────────────────────────────────────────────────────────────
# AFFICHAGE
# ──────────────────────────────────────────────────────────────────────────────
def print_summary(results: list[dict]) -> None:
    print("\n")
    print("═" * 90)
    print("  📊  RÉSUMÉ DU BENCHMARK — AGENTIC RAG")
    print("═" * 90)
    print(f"  {'Modèle':<32} {'Catégorie':<22} {'RPD':>6} {'Score':>8}  {'Statut'}")
    print("─" * 90)

    for r in sorted(results, key=lambda x: x.get("overall_score", -1), reverse=True):
        score = r.get("overall_score", 0)
        max_s = r.get("max_score", 14)
        pct = f"{score}/{max_s}" if max_s > 0 else "N/A"
        status = r.get("status", "OK")
        icon = "✅" if status == "OK" else ("⛔" if "QUOTA" in status else "❌")
        print(f"  {icon} {r['model']:<30} {r['category']:<22} {str(r['rpd']):>6} {pct:>8}  {r.get('warning','')[:35]}")

    print("─" * 90)
    print("\n  🎯  RECOMMANDATIONS POUR TON RAG :\n")
    print("  1. DÉVELOPPEMENT INTENSIF  → gemma-3-27b-it  (14 400 RPD, bon équilibre)")
    print("  2. QUALITÉ DE PROD         → gemma-4-26b-it  (1 500 RPD, raisonnement avancé)")
    print("  3. GRADING ÉCONOMIQUE      → gemini-3.1-flash-lite-preview (500 RPD, yes/no)")
    print("  4. ÉVITER               → gemini-2.5-flash / gemini-3-flash (20 RPD)")
    print()


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Benchmark tous les modèles Gemini/Gemma pour l'Agentic RAG")
    parser.add_argument(
        "--models", nargs="+", default=list(ALL_MODELS.keys()),
        help="Modèles à tester (défaut: tous)"
    )
    parser.add_argument(
        "--output", default="results/benchmark_results.json",
        help="Fichier de sortie JSON"
    )
    parser.add_argument(
        "--skip-high-quality", action="store_true",
        help="Ignore les modèles à 20 RPD (gemini-2.5-flash, gemini-3-flash)"
    )
    args = parser.parse_args()

    cfg = get_settings()
    if not cfg.gemini_api_key:
        print("❌ GEMINI_API_KEY manquant dans .env")
        sys.exit(1)

    models_to_test = args.models
    if args.skip_high_quality:
        models_to_test = [m for m in models_to_test if ALL_MODELS.get(m, {}).get("rpd", 999) > 20]
        print("⚡ Mode --skip-high-quality : modèles à 20 RPD ignorés")

    print(f"\n🚀 Benchmark Agentic RAG — {len(models_to_test)} modèles")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔑 Clé API : {cfg.gemini_api_key[:8]}...")
    print("=" * 70)

    all_results = []
    for i, model in enumerate(models_to_test, 1):
        info = ALL_MODELS.get(model, {})
        print(f"\n[{i}/{len(models_to_test)}] 🤖 {model}")
        print(f"    📋 {info.get('profile', 'profil inconnu')}")
        print(f"    📊 RPD: {info.get('rpd', '?')} | RPM: {info.get('rpm', '?')}")
        print(f"    {info.get('warning', '')}")

        result = test_model(model, cfg.gemini_api_key)
        all_results.append(result)

        # Délai entre modèles pour éviter les rate limits
        if i < len(models_to_test):
            print(f"    ⏳ Pause 3s avant le prochain modèle...")
            time.sleep(3)

    # Sauvegarde JSON
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "results": all_results,
        }, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Résultats sauvegardés : {output_path}")

    print_summary(all_results)


if __name__ == "__main__":
    main()
