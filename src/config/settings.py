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
    bm25_store: str = "vector_store/bm25"
    books_metadata: str = "results/metadata/books_metadata.json"


class EmbeddingsConfig(BaseModel):
    model_name: str
    device: str = "cpu"
    normalize: bool = True
    batch_size: int = 32
    query_prefix: str = ""
    passage_prefix: str = ""


class ChunkingConfig(BaseModel):
    strategy: str = "recursive"          # semantic | recursive
    chunk_size: int = 1500
    chunk_overlap: int = 150
    separators: list[str] = Field(default_factory=lambda: ["\n\n", "\n", " ", ""])
    # Semantic chunker params (used only when strategy == "semantic")
    semantic_breakpoint_type: str = "percentile"
    semantic_breakpoint_amount: float = 95.0
    semantic_buffer_size: int = 1
    # Post-processing (any strategy)
    min_chunk_chars: int = 200
    max_chunk_chars: int = 2000


class FiltersConfig(BaseModel):
    enable_pathological_filter: bool = True
    min_alpha_ratio: float = 0.5
    min_vocab_diversity: float = 0.3
    enable_dedup: bool = True
    dedup_jaccard_threshold: float = 0.85
    dedup_num_perm: int = 128


class HeaderFooterConfig(BaseModel):
    enable: bool = True
    occurrence_ratio: float = 0.3
    scan_first_lines: int = 3
    scan_last_lines: int = 3


class VectorStoreConfig(BaseModel):
    provider: str = "chroma"
    collection_name: str
    persist_directory: str
    distance: str = "cosine"


class HybridConfig(BaseModel):
    enable: bool = True
    dense_weight: float = 1.0
    sparse_weight: float = 1.0
    rrf_k: int = 60


class MMRConfig(BaseModel):
    enable: bool = True
    lambda_mult: float = 0.6
    candidates_after_mmr: int = 15


class RerankerConfig(BaseModel):
    enable: bool = True
    model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    device: str = "cpu"
    batch_size: int = 32


class RetrievalConfig(BaseModel):
    top_k: int = 5
    fetch_k: int = 30
    score_threshold: float = 0.0
    hybrid: HybridConfig = Field(default_factory=HybridConfig)
    mmr: MMRConfig = Field(default_factory=MMRConfig)
    reranker: RerankerConfig = Field(default_factory=RerankerConfig)
    # Legacy compatibility (read by older code paths)
    use_mmr: bool = True
    mmr_lambda: float = 0.5


class LLMConfig(BaseModel):
    provider: str = "gemini"
    model_name: str = "gemini-2.5-flash"
    temperature: float = 0.2
    max_output_tokens: int = 2048
    top_p: float = 0.95
    # Timeout (s) per request to the LLM provider. Prevents indefinite hangs
    # when the API stalls (observed on long prompts / flaky network).
    timeout: float = 60.0
    # Max automatic retries on transient errors (network / 5xx / timeout).
    max_retries: int = 2


class ReActConfig(BaseModel):
    max_tool_calls: int = 5


class ReActConfig(BaseModel):
    max_tool_calls: int = 5


class AgentConfig(BaseModel):
    max_iterations: int = 6
    enable_query_rewriting: bool = True
    enable_grading: bool = True
    verbose: bool = True
    enable_router: bool = True
    router_default: str = "simple"
    react: ReActConfig = Field(default_factory=ReActConfig)


class EvaluationConfig(BaseModel):
    testset_path: str = "results/eval/testset.json"
    results_dir: str = "results/eval"
    testset_size: int = 50
<<<<<<< HEAD
    judge_model: str = "gemini-3.1-flash-lite"
    judge_rpm: int = 12          # cap requests-per-minute on the judge
=======
    judge_model: str = "gemini-2.5-flash"
>>>>>>> origin/main
    metrics: list[str] = Field(
        default_factory=lambda: [
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
        ]
    )


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
    filters: FiltersConfig = Field(default_factory=FiltersConfig)
    header_footer: HeaderFooterConfig = Field(default_factory=HeaderFooterConfig)
    vector_store: VectorStoreConfig
    retrieval: RetrievalConfig
    llm: LLMConfig
    agent: AgentConfig
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)

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
