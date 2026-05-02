"""Generic file IO helpers."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def text_hash(text: str) -> str:
    """Stable hash for text content (used as cache key).

    Uses errors='replace' to survive any unpaired surrogates that escaped
    cleaning — better to hash a slightly mangled string than to crash.
    """
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_jsonl(path: str | Path, records: Iterable[dict[str, Any]]) -> int:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with p.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n += 1
    return n


def read_jsonl(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)
