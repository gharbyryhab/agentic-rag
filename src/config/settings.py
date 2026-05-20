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
    timeout_s: float = 60.0  # wall-clock cap on the full graph.stream() call


class AgentConfig(BaseModel):
    max_iterations: int = 6
    enable_query_rewriting: bool = True
    enable_grading: bool = True
    enable_web_fallback: bool = True  # DuckDuckGo fallback when KB returns no relevant docs
    verbose: bool = True
    enable_router: bool = True
    router_default: str = "simple"
    react: ReActConfig = Field(default_factory=ReActConfig)


class TestsetGenConfig(BaseModel):
    """Parameters for testset generation strategies."""
    multi_chunks_per_qa: int = 3      # nb chunks combined for "multi" strategy
    sample_factor: int = 3            # over-sampling factor (target × this)
    # ─── Knowledge-graph cache (strategy=ragas) ──────────────────────────────
    # When set, the KG built by Ragas is saved here after construction and can
    # be reloaded via --reuse-kg to skip the expensive extraction phase
    # (Opt 1 : -80% tokens on subsequent runs).
    kg_cache_path: str = "results/eval/kg.json"


class SynthesizerConfig(BaseModel):
    """Synthesizer = LLM used to generate the testset (strategy=ragas).
    Recommended : 'groq' with openai/gpt-oss-120b — OpenAI-tuned for reliable
    structured JSON outputs (Ragas extractors require strict JSON, and
    llama-4-scout fails this consistency check). Compensate the 200K TPD/key
    via multi-key rotation (GROQ_API_KEYS)."""
    provider: str = "groq"                   # groq | gemini
    model: str = "openai/gpt-oss-120b"
    rpm: int = 30                            # Groq free tier RPM limit
    tpm: int = 8000                          # Groq free tier TPM limit for gpt-oss-120b


class JudgeConfig(BaseModel):
    """Judge = LLM used by Ragas to score answers.
    Recommended provider: 'groq' with llama-3.3-70b-versatile (high judgment quality)."""
    provider: str = "groq"                   # groq | gemini
    model: str = "llama-3.3-70b-versatile"
    rpm: int = 30                            # Groq free tier RPM limit
    tpm: int = 12000                         # Groq free tier TPM limit (tokens/min)


class OnlineEvalConfig(BaseModel):
    enabled: bool = True
    sample_rate: float = 0.15          # fraction of live questions to evaluate
    log_path: str = "results/logs/runtime_quality.jsonl"


class EvaluationConfig(BaseModel):
    testset_path: str = "results/eval/testset.json"
    results_dir: str = "results/eval"
    testset_size: int = 50

    # Legacy fields (kept for backward compat, but prefer the new sub-models below)
    judge_model: str = "llama-3.3-70b-versatile"
    judge_rpm: int = 30

    # New structured config (used by tools/eval/*.py)
    synthesizer: SynthesizerConfig = Field(default_factory=SynthesizerConfig)
    judge: JudgeConfig = Field(default_factory=JudgeConfig)
    testset_gen: TestsetGenConfig = Field(default_factory=TestsetGenConfig)

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
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    # Optional comma-separated list of additional Groq keys for automatic
    # rotation on TPD exhaustion. Example : GROQ_API_KEYS=gsk_a,gsk_b,gsk_c
    groq_api_keys: str = Field(default="", alias="GROQ_API_KEYS")
    hf_token: str = Field(default="", alias="HF_TOKEN")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    env: str = Field(default="development", alias="ENV")

    def get_groq_keys(self) -> list[str]:
        """Return ALL configured Groq keys in order : GROQ_API_KEYS first, then
        the fallback GROQ_API_KEY if not already in the list. Used by the
        key-rotating client to walk down the list on TPD exhaustion."""
        out: list[str] = []
        if self.groq_api_keys:
            out.extend(k.strip() for k in self.groq_api_keys.split(",") if k.strip())
        if self.groq_api_key and self.groq_api_key.strip() not in out:
            out.append(self.groq_api_key.strip())
        return out

    # YAML config
    online_eval: OnlineEvalConfig = Field(default_factory=OnlineEvalConfig)
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
