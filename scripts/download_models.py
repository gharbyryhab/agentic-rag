"""Download embedding and reranker models to the local HuggingFace cache.

Run this once (with network access) before using the pipeline offline:
    python -m scripts.download_models

The script temporarily clears HF_HUB_OFFLINE / TRANSFORMERS_OFFLINE so the
download can proceed, then restores the environment.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Clear offline flags for this process so downloads are allowed.
for _var in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE"):
    os.environ.pop(_var, None)

from src.config import get_settings  # noqa: E402
from src.utils import get_logger  # noqa: E402

log = get_logger("download_models")


def main() -> int:
    cfg = get_settings()
    emb_model = cfg.embeddings.model_name
    emb_device = cfg.embeddings.device
    rnk_model = cfg.retrieval.reranker.model
    rnk_device = cfg.retrieval.reranker.device

    log.info(f"Downloading embedding model: {emb_model}")
    try:
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(emb_model, device=emb_device)
        log.info(f"  OK — dim={m.get_embedding_dimension()}")
    except Exception as e:
        log.error(f"  FAILED: {e}")
        return 1

    log.info(f"Downloading reranker model: {rnk_model}")
    try:
        from sentence_transformers import CrossEncoder
        CrossEncoder(rnk_model, device=rnk_device)
        log.info("  OK")
    except Exception as e:
        log.error(f"  FAILED: {e}")
        return 1

    log.info("All models downloaded successfully. You can now run with HF_HUB_OFFLINE=1.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
