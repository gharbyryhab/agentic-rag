"""Centralized configuration — merges YAML + .env via pydantic."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT_DIR / "config" / "config.yaml"
PROMPTS_PATH = ROOT_DIR / "config" / "prompts.yaml"

load_dotenv(ROOT_DIR / ".env")


# ---------- Sub-models ----------
class PathsConfig(BaseModel):
    data_raw: str
    data_processed: str
    data_chunks: str
    vector_store: str
    embedding_cache: str
    logs: str


class EmbeddingsConfig(BaseModel):
    model_name: str
    device: str = "cpu"
    normalize: bool = True
    batch_size: int = 32
    query_prefix: str = ""
    passage_prefix: str = ""


class ChunkingConfig(BaseModel):
    strategy: str = "recursive"
    chunk_size: int = 800
    chunk_overlap: int = 120
    separators: list[str] = Field(default_factory=lambda: ["\n\n", "\n", " ", ""])


class VectorStoreConfig(BaseModel):
    provider: str = "chroma"
    collection_name: str
    persist_directory: str
    distance: str = "cosine"


class RetrievalConfig(BaseModel):
    top_k: int = 5
    score_threshold: float = 0.0
    use_mmr: bool = True
    mmr_lambda: float = 0.5
    fetch_k: int = 20


class LLMConfig(BaseModel):
    provider: str = "gemini"
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_output_tokens: int = 2048
    top_p: float = 0.95


class AgentConfig(BaseModel):
    max_iterations: int = 6
    enable_query_rewriting: bool = True
    enable_grading: bool = True
    verbose: bool = True


# ---------- Root settings ----------
class Settings(BaseSettings):
    """Aggregated configuration object."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Secrets / env
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    hf_token: str = Field(default="", alias="HF_TOKEN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    env: str = Field(default="development", alias="ENV")

    # YAML config
    paths: PathsConfig
    embeddings: EmbeddingsConfig
    chunking: ChunkingConfig
    vector_store: VectorStoreConfig
    retrieval: RetrievalConfig
    llm: LLMConfig
    agent: AgentConfig

    # Project root (for resolving relative paths)
    root_dir: Path = ROOT_DIR

    def absolute_path(self, relative: str) -> Path:
        """Resolve a config-relative path to an absolute one."""
        return (self.root_dir / relative).resolve()


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache the settings singleton."""
    yaml_cfg = _load_yaml(CONFIG_PATH)
    return Settings(**yaml_cfg)


@lru_cache(maxsize=1)
def get_prompts() -> dict[str, str]:
    """Load prompt templates."""
    return _load_yaml(PROMPTS_PATH)
