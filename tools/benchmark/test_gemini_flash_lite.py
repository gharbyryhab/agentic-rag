"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  TEST — gemini-3.1-flash-lite-preview                                        ║
║  Catégorie : LLM léger | RPD: 500 | RPM: 15                                 ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  UTILITÉ POUR TON AGENTIC RAG :                                              ║
║  → SPÉCIALISÉ pour le GRADING — tâche répétitive (oui/non par chunk)        ║
║  → Architecture hybride possible : Lite pour grade, Gemma4 pour generate     ║
║  → Très rapide et économique pour les filtres de pertinence                  ║
║  → 500 RPD → si on l'utilise que pour grade: ~1 666 questions/jour           ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage :
    python -m scripts.test_gemini_flash_lite
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # ← parents[2] car on est 2 niveaux plus profondsys.path.insert(0, str(ROOT))

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from src.config import get_settings

MODEL = "gemini-3.1-flash-lite-preview"
RPD = 500
RPM = 15

GRADE_SYSTEM = """You are a grader assessing relevance of a retrieved document to a user question.
If the document contains keywords or semantic meaning related to the question, grade it as relevant.
Output a single word: "yes" or "no"."""

# 10 cas de grading variés — représentatifs de tes 101 books
GRADE_CASES = [
    # (document, question, expected)
    ("Support Vector Machines find the optimal hyperplane that maximizes margin between classes. The kernel trick allows non-linear boundaries via RBF, polynomial kernels.",
     "How does SVM separate non-linearly separable data?", "yes"),

    ("The Python language was created in 1991. It features simple, readable syntax and is used in web development.",
     "How does SVM separate non-linearly separable data?", "no"),

    ("Convolutional Neural Networks use filters that slide over input data. Each filter detects specific features like edges, textures. Pooling reduces spatial dimensions.",
     "Explain how CNNs detect features in images", "yes"),

    ("Principal Component Analysis (PCA) reduces dimensionality by projecting data onto principal components — directions of maximum variance in the dataset.",
     "What is PCA and how does it reduce dimensionality?", "yes"),

    ("The Great Wall of China was built over many centuries. It stretches over 13,000 miles across northern China.",
     "What is PCA and how does it reduce dimensionality?", "no"),

    ("K-means clustering partitions n observations into k clusters. Each observation belongs to the cluster with the nearest centroid. The algorithm iterates until convergence.",
     "How does gradient boosting work?", "no"),

    ("XGBoost builds an ensemble of decision trees sequentially. Each new tree corrects errors of the previous ensemble by fitting residuals. Uses gradient descent in function space.",
     "How does gradient boosting work?", "yes"),

    ("The Adam optimizer combines momentum and RMSprop. It maintains per-parameter learning rates and exponential moving averages of gradients.",
     "What are the advantages of Adam over SGD?", "yes"),

    ("Pandas provides DataFrame objects for tabular data manipulation. Common operations include groupby, merge, pivot_table.",
     "What are the advantages of Adam over SGD?", "no"),

    ("Recurrent Neural Networks process sequential data by maintaining a hidden state. LSTMs and GRUs solve the vanishing gradient problem with gating mechanisms.",
     "How do LSTMs address the vanishing gradient problem?", "yes"),
]


def run_test():
    cfg = get_settings()
    if not cfg.gemini_api_key:
        print("❌ GEMINI_API_KEY manquant dans .env")
        sys.exit(1)

    llm = ChatGoogleGenerativeAI(
        model=MODEL,
        google_api_key=cfg.gemini_api_key,
        temperature=0.0,   # Grading = déterministe, pas de créativité
        max_output_tokens=10,  # On attend juste "yes" ou "no"
        top_p=1.0,
    )

    print(f"\n{'='*65}")
    print(f"  🤖  TEST MODÈLE : {MODEL}")
    print(f"  📊  RPD: {RPD} | RPM: {RPM}")
    print(f"  🎯  Profil : Tâche GRADING — filtrage rapide et économique")
    print(f"{'='*65}\n")

    print("🎯 TEST GRADING INTENSIF — 10 cas (5 pertinents, 5 non pertinents)\n")
    print("   Ce test mesure la précision du modèle sur sa tâche principale :\n")
    print("   filtrer les chunks non pertinents avant la génération RAG.\n")
    print(f"   {'N°':<4} {'Attendu':<10} {'Reçu':<15} {'✓':<5} {'Latence'}")
    print("   " + "─" * 50)

    correct = 0
    false_pos = 0  # dit "yes" mais c'était "no"
    false_neg = 0  # dit "no" mais c'était "yes"
    latencies = []

    for i, (doc, q, expected) in enumerate(GRADE_CASES, 1):
        msgs = [
            SystemMessage(content=GRADE_SYSTEM),
            HumanMessage(content=f"Document:\n{doc}\n\nQuestion: {q}\n\nIs this document relevant?"),
        ]
        try:
            t0 = time.perf_counter()
            result = llm.invoke(msgs)
            lat = time.perf_counter() - t0
            latencies.append(lat)

            verdict = (result.content if isinstance(result.content, str) else str(result.content)).strip().lower()
            verdict_clean = "yes" if verdict.startswith("y") else "no"
            ok = verdict_clean == expected

            if ok:
                correct += 1
            elif verdict_clean == "yes" and expected == "no":
                false_pos += 1
            elif verdict_clean == "no" and expected == "yes":
                false_neg += 1

            icon = "✅" if ok else "❌"
            print(f"   [{i:02d}] {expected:<10} {verdict[:12]:<15} {icon:<5} {lat:.2f}s")
            time.sleep(1)  # respecter RPM=15

        except Exception as e:
            err = str(e)
            print(f"   [{i:02d}] ❌ ERREUR : {err[:60]}")
            if "429" in err:
                print("   ⚠️  Rate limit — pause 60s...")
                time.sleep(60)

    # ── Résumé ────────────────────────────────────────────────────────────────
    accuracy = correct / len(GRADE_CASES) * 100
    avg_lat = sum(latencies) / len(latencies) if latencies else 0
    precision = correct / (correct + false_pos) * 100 if (correct + false_pos) > 0 else 0
    recall = correct / (correct + false_neg) * 100 if (correct + false_neg) > 0 else 0

    print(f"\n   {'─'*50}")
    print(f"   📊 RÉSULTATS GRADING ({MODEL}) :\n")
    print(f"      Accuracy   : {accuracy:.0f}%  ({correct}/{len(GRADE_CASES)} corrects)")
    print(f"      Faux positifs : {false_pos}  (dit 'yes' alors que 'no')")
    print(f"      Faux négatifs : {false_neg}  (dit 'no' alors que 'yes')")
    print(f"      Precision  : {precision:.0f}%")
    print(f"      Recall     : {recall:.0f}%")
    print(f"      Latence moy: {avg_lat:.2f}s")

    # Interprétation
    print(f"\n   💡 Interprétation pour ton RAG :")
    if accuracy >= 90:
        print(f"      ✅ EXCELLENT — utilise ce modèle pour le grading")
        print(f"      💰 Budget grading : 500 RPD → ~1 666 questions/jour")
    elif accuracy >= 75:
        print(f"      ⚠️  CORRECT — viable mais surveille les faux négatifs")
        print(f"         ({false_neg} chunks pertinents perdus sur 10)")
    else:
        print(f"      ❌ INSUFFISANT — utilise gemma-3-27b-it pour le grading")

    if false_neg > 2:
        print(f"\n   ⚠️  {false_neg} faux négatifs → le grader filtre trop agressivement")
        print(f"      → Risque : l'agent ne trouve pas assez de contexte pour répondre")

    print(f"\n{'='*65}")
    print(f"  🏃 {MODEL} — Architecture hybride suggérée :")
    print(f"  GRADING   → {MODEL}  (500 RPD, rapide, économique)")
    print(f"  GENERATE  → gemma-4-26b-it  (1 500 RPD, qualité)")
    print(f"  Capacité  : min(500÷3, 1500÷2) ≈ 166 questions/jour en hybride")
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
            print("⚠️  Quota — attends 60s.")
        elif "404" in err:
            print("⚠️  Modèle introuvable (preview).")


if __name__ == "__main__":
    main()
