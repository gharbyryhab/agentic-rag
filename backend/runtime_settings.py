"""
In-memory runtime settings overlay.

Default values come from config.yaml. Admins can override them via PATCH /admin/settings,
which persists changes to the app_settings DB table and updates this singleton so they
take effect immediately without restarting the server.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# ── Defaults (mirrors config/config.yaml) ─────────────────────────────────────

_DEFAULTS: dict[str, Any] = {
    "model_name": "gemma-4-27b-it",
    "temperature": 0.7,
    "top_k": 5,
    "max_sources": 5,
}

_store: dict[str, Any] = dict(_DEFAULTS)

# Try to pull defaults from config.yaml if it exists
_cfg_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
if _cfg_path.exists():
    try:
        import yaml
        with _cfg_path.open() as f:
            _cfg = yaml.safe_load(f) or {}
        _llm = _cfg.get("llm", {})
        _ret = _cfg.get("retrieval", {})
        if _llm.get("model"):
            _store["model_name"] = str(_llm["model"])
        if _llm.get("temperature") is not None:
            _store["temperature"] = float(_llm["temperature"])
        if _ret.get("top_k") is not None:
            _store["top_k"] = int(_ret["top_k"])
        if _ret.get("max_sources") is not None:
            _store["max_sources"] = int(_ret["max_sources"])
    except Exception as e:
        log.warning("runtime_settings: could not load config.yaml defaults: %s", e)


def get(key: str) -> Any:
    return _store.get(key, _DEFAULTS.get(key))


def get_all() -> dict[str, Any]:
    return dict(_store)


def set_many(updates: dict[str, Any]) -> None:
    """Update in-memory values (call after persisting to DB)."""
    _CAST: dict[str, type] = {
        "model_name": str,
        "temperature": float,
        "top_k": int,
        "max_sources": int,
    }
    for k, v in updates.items():
        if k in _CAST and v is not None:
            _store[k] = _CAST[k](v)


async def load_from_db(db) -> None:
    """Called at startup to restore any persisted overrides from the DB."""
    from sqlalchemy import select
    from backend.models import AppSetting

    try:
        rows = (await db.execute(select(AppSetting))).scalars().all()
        overrides = {r.key: r.value for r in rows}
        set_many(overrides)
        log.info("runtime_settings: loaded %d overrides from DB", len(overrides))
    except Exception as e:
        log.warning("runtime_settings: could not load from DB: %s", e)
