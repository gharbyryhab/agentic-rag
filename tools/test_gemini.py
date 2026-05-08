"""
Test minimal Gemini — utilise le GeminiClient du projet.

Usage:
    python -m scripts.test_gemini
    python -m scripts.test_gemini "Explique le ML en 2 phrases"
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.llm.gemini_client import GeminiClient

def main():
    prompt = " ".join(sys.argv[1:]) or "Dis bonjour en 1 phrase et confirme que tu fonctionnes."

    print(f"\n💬 Prompt : {prompt}")
    print("-" * 60)

    try:
        llm = GeminiClient()
        response = llm.generate(prompt)
        print(response)
        print("-" * 60)
        print("✅ Gemini répond — quota OK.")

    except Exception as e:
        err = str(e)
        print(f"❌ Erreur : {err}")

        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            if "PerDay" in err or "PerDayPerProject" in err:
                print("\n⚠️  Quota JOURNALIER épuisé → attends minuit UTC.")
            else:
                print("\n⚠️  Quota PAR MINUTE dépassé → attends 60s et relance.")
        elif "API_KEY" in err or "invalid" in err.lower():
            print("\n⚠️  Clé API invalide. Vérifie ton .env")

if __name__ == "__main__":
    main()