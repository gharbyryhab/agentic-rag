"""Shared token-aware rate limiter for Groq / Gemini calls.

Why this module exists
----------------------
Groq's free tier enforces TWO limits per minute :
  - RPM (requests per minute)        : e.g. 30
  - TPM (tokens per minute)          : e.g. 8000 for openai/gpt-oss-120b

The simple RPM-only limiter that was previously in `run_ragas.py` could not
prevent 429 errors when:
  - several workers ran in parallel and each call consumed ~2000 tokens
    → 3 workers × 2000 tokens in < 5s → 6000 tokens → cumulated with the
      previous bucket → > 8000 TPM → 429
  - long prompts (knowledge-graph extraction in Ragas TestsetGenerator)
    spike the token cost unpredictably

The fix is a **sliding-window token bucket** that:
  1. Tracks every call (timestamp + estimated tokens) in a 60-second window
  2. Blocks BEFORE a call if adding it would exceed RPM or TPM
  3. Wraps the LLM client (ChatGroq / ChatGoogleGenerativeAI) to acquire
     a slot before every `_generate` / `_agenerate`
  4. On a 429 (slipped through anyway), parses the suggested wait time
     from the error message and sleeps that long with jitter

This module is provider-agnostic — `acquire()` is just a slot allocator.
"""
from __future__ import annotations

import asyncio
import logging
import random
import re
import threading
import time
from collections import deque

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Token estimation
# ──────────────────────────────────────────────────────────────────────────────

def estimate_tokens(messages) -> int:
    """Rough token count : ~4 chars per token (good enough for English / code).

    Works on a single string, a list of LangChain messages, or a list of dicts.
    Adds a small overhead per message (role/separator tokens).
    """
    if isinstance(messages, str):
        return max(1, len(messages) // 4) + 4

    total = 0
    seq = messages if isinstance(messages, (list, tuple)) else [messages]

    for m in seq:
        # LangChain BaseMessage
        if hasattr(m, "content"):
            content = m.content
        elif isinstance(m, dict):
            content = m.get("content", "")
        else:
            content = str(m)

        if isinstance(content, str):
            total += len(content) // 4
        elif isinstance(content, list):
            # multimodal blocks
            for block in content:
                if isinstance(block, dict):
                    txt = block.get("text") or block.get("thinking") or ""
                    total += len(str(txt)) // 4
                elif isinstance(block, str):
                    total += len(block) // 4
        total += 4  # per-message overhead

    return max(1, total)


# ──────────────────────────────────────────────────────────────────────────────
# Sliding-window token bucket
# ──────────────────────────────────────────────────────────────────────────────

class TokenBucketRateLimiter:
    """Thread-safe RPM + TPM rate limiter using a 60-second sliding window.

    Optimizations vs naive limiter :
      - safety_margin = 0.92 (was 0.85) → +8% throughput, still safe with backoff
      - adaptive output estimation : we observe the ACTUAL output tokens of
        recent calls (via `report_actual_tokens()`) and use a sliding average,
        instead of over-reserving the max_tokens hard cap.
      - over-reservation correction : after the call, if actual << estimated,
        the freed-up tokens are released early back to the window.

    Args:
        rpm: max requests per minute (set to a high value to disable).
        tpm: max tokens per minute (set to 0 to disable TPM tracking).
        safety_margin: use only this fraction of the limits (default 0.92).
        default_output_budget: how many output tokens to assume per call when
            we have no observation yet (default 600 — covers Ragas extractors).
    """

    def __init__(self, rpm: int = 30, tpm: int = 8000,
                 safety_margin: float = 0.92,
                 default_output_budget: int = 600) -> None:
        self.rpm_cap = max(1, int(rpm * safety_margin))
        self.tpm_cap = max(0, int(tpm * safety_margin))
        # Sliding window : (timestamp, reserved_tokens) for last 60 seconds.
        # `reserved_tokens` is initially our estimate, then patched downward
        # when the real usage comes back via report_actual_tokens().
        self._events: deque[list] = deque()  # mutable lists so we can patch tokens
        self._lock = threading.Lock()
        # Adaptive output learning : rolling window of last 30 observed outputs
        self._recent_outputs: deque[int] = deque(maxlen=30)
        self._default_output = max(50, int(default_output_budget))

    # ---------- adaptive output estimation ----------
    def expected_output_tokens(self) -> int:
        """Best-guess output budget : sliding average of recent observed outputs,
        plus a 30% margin. Falls back to `default_output_budget` if no data."""
        if len(self._recent_outputs) >= 3:
            avg = sum(self._recent_outputs) / len(self._recent_outputs)
            return max(self._default_output // 2, int(avg * 1.3))
        return self._default_output

    def report_actual_tokens(self, reserved: int, actual: int,
                             output_only: int | None = None) -> None:
        """Feed back actual usage so future estimates auto-correct.

        Args:
            reserved: tokens we reserved before the call (returned by acquire)
            actual: total tokens the API actually consumed
            output_only: just the completion tokens (preferred for learning)
        """
        with self._lock:
            # Learn from output observations
            if output_only is not None and output_only > 0:
                self._recent_outputs.append(output_only)
            # Patch the most recent event : reclaim over-reserved tokens
            if actual < reserved and self._events:
                # find a matching event (LIFO is fine — usually last is ours)
                for ev in reversed(self._events):
                    if ev[1] == reserved:
                        ev[1] = actual
                        break

    # ---------- internals ----------
    def _evict_old(self, now: float) -> None:
        """Drop events older than 60s. Caller holds the lock."""
        cutoff = now - 60.0
        while self._events and self._events[0][0] < cutoff:
            self._events.popleft()

    def _current_usage(self) -> tuple[int, int]:
        """(requests, tokens) currently in the window. Caller holds the lock."""
        return len(self._events), sum(t for _, t in self._events)

    def _compute_wait(self, now: float, need_tokens: int) -> float:
        """Time (s) to wait until both RPM and TPM headroom exist."""
        # Find the smallest set of front-of-window events whose removal frees
        # enough capacity.
        n_req, n_tok = self._current_usage()

        # How much do we need to expire (in tokens or requests) ?
        req_excess = max(0, n_req + 1 - self.rpm_cap)
        tok_excess = max(0, n_tok + need_tokens - self.tpm_cap) if self.tpm_cap > 0 else 0

        if req_excess == 0 and tok_excess == 0:
            return 0.0

        # Walk the window from oldest to newest, accumulating freed capacity
        freed_req = 0
        freed_tok = 0
        for ts, tok in self._events:
            freed_req += 1
            freed_tok += tok
            if freed_req >= req_excess and freed_tok >= tok_excess:
                # ts is the timestamp of the event that needs to expire
                return max(0.0, ts + 60.0 - now)
        # If we exhaust the window and still can't fit, wait the longest
        return max(0.0, (self._events[0][0] + 60.0) - now) if self._events else 1.0

    # ---------- public ----------
    def acquire(self, tokens_estimate: int) -> int:
        """Block until a request of `tokens_estimate` tokens fits in the window.
        Returns the reserved token count (= tokens_estimate) so the caller
        can later `report_actual_tokens(reserved=..., actual=...)`."""
        while True:
            with self._lock:
                now = time.monotonic()
                self._evict_old(now)
                wait = self._compute_wait(now, tokens_estimate)
                if wait <= 0:
                    # Reserve the slot — use a list so it can be patched later
                    self._events.append([now, tokens_estimate])
                    return tokens_estimate
            # Sleep OUTSIDE the lock — small jitter to avoid thundering-herd
            time.sleep(wait + random.uniform(0.05, 0.3))

    async def aacquire(self, tokens_estimate: int) -> int:
        """Async equivalent of `acquire`."""
        while True:
            with self._lock:
                now = time.monotonic()
                self._evict_old(now)
                wait = self._compute_wait(now, tokens_estimate)
                if wait <= 0:
                    self._events.append([now, tokens_estimate])
                    return tokens_estimate
            await asyncio.sleep(wait + random.uniform(0.05, 0.3))


# ──────────────────────────────────────────────────────────────────────────────
# Extract real token usage from a LangChain ChatResult
# ──────────────────────────────────────────────────────────────────────────────

def extract_token_usage(result) -> tuple[int, int]:
    """Pull (total_tokens, completion_tokens) out of a LangChain ChatResult /
    AIMessage / response_metadata. Returns (0, 0) if we can't find them.

    Groq returns token_usage in result.llm_output['token_usage'] or in
    each generation's generation_info['token_usage'].
    """
    try:
        # 1) ChatResult.llm_output
        llm_output = getattr(result, "llm_output", None)
        if isinstance(llm_output, dict):
            usage = llm_output.get("token_usage") or llm_output.get("usage", {})
            if usage:
                return (
                    int(usage.get("total_tokens", 0)),
                    int(usage.get("completion_tokens", 0)),
                )

        # 2) Walk generations
        gens = getattr(result, "generations", None) or []
        for g in gens:
            if isinstance(g, list):
                g = g[0] if g else None
            if g is None:
                continue
            info = getattr(g, "generation_info", None) or {}
            usage = info.get("token_usage") or info.get("usage", {})
            if usage:
                return (
                    int(usage.get("total_tokens", 0)),
                    int(usage.get("completion_tokens", 0)),
                )
            # AIMessage.usage_metadata (newer LangChain)
            msg = getattr(g, "message", None)
            if msg is not None:
                meta = getattr(msg, "usage_metadata", None) or {}
                if meta:
                    total = int(meta.get("total_tokens", 0))
                    output = int(meta.get("output_tokens", 0))
                    return (total, output)
    except Exception:  # noqa: BLE001
        pass
    return (0, 0)


# ──────────────────────────────────────────────────────────────────────────────
# 429 adaptive backoff
# ──────────────────────────────────────────────────────────────────────────────

_TRY_AGAIN_RE = re.compile(r"try again in ([\d.]+)\s*s", re.IGNORECASE)
_RETRY_AFTER_RE = re.compile(r"retry[\s\-]?after[: ]+([\d.]+)", re.IGNORECASE)


def parse_retry_after(error_message: str) -> float | None:
    """Extract the suggested retry delay from a 429 error message.

    Groq's 429 looks like : "Please try again in 3.915s"
    OpenAI-like sometimes uses : "Retry-After: 8"
    """
    for pat in (_TRY_AGAIN_RE, _RETRY_AFTER_RE):
        m = pat.search(error_message)
        if m:
            try:
                return float(m.group(1))
            except (ValueError, TypeError):
                continue
    return None


def is_rate_limit_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return (
        "429" in msg
        or "rate_limit" in msg
        or "ratelimit" in msg
        or "too many requests" in msg
    )


def is_tpd_error(exc: BaseException) -> bool:
    """Detect a 'tokens per day' (TPD) limit error vs a TPM (per minute) one.

    TPD looks like:
        "Rate limit reached ... on tokens per day (TPD): Limit 200000, Used ..."
    TPM looks like:
        "Rate limit reached ... on tokens per minute (TPM): Limit 8000, ..."

    Distinguishing matters because TPD requires KEY ROTATION (not just waiting),
    while TPM can be solved by sleeping a few seconds.
    """
    if not is_rate_limit_error(exc):
        return False
    msg = str(exc).lower()
    return (
        "per day" in msg
        or "(tpd)" in msg
        or "tokens per day" in msg
        or "requests per day" in msg
        or "(rpd)" in msg
    )


def call_with_backoff(fn, *args, max_attempts: int = 6, base_wait: float = 5.0,
                      max_wait: float = 90.0, **kwargs):
    """Sync wrapper that retries on 429 with exponential backoff + suggested delay."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            if not is_rate_limit_error(e) or attempt == max_attempts:
                raise
            suggested = parse_retry_after(str(e))
            backoff = min(max_wait, base_wait * (2 ** (attempt - 1)))
            wait = max(suggested + 1.5 if suggested else 0.0, backoff)
            wait += random.uniform(0.5, 2.0)  # jitter
            log.warning(
                f"Rate-limit 429 (attempt {attempt}/{max_attempts}). "
                f"Suggested={suggested}s, sleeping {wait:.1f}s…"
            )
            time.sleep(wait)
    raise RuntimeError("call_with_backoff: exhausted retries")


async def acall_with_backoff(fn, *args, max_attempts: int = 6, base_wait: float = 5.0,
                             max_wait: float = 90.0, **kwargs):
    """Async equivalent of `call_with_backoff`."""
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            if not is_rate_limit_error(e) or attempt == max_attempts:
                raise
            suggested = parse_retry_after(str(e))
            backoff = min(max_wait, base_wait * (2 ** (attempt - 1)))
            wait = max(suggested + 1.5 if suggested else 0.0, backoff)
            wait += random.uniform(0.5, 2.0)
            log.warning(
                f"Rate-limit 429 (attempt {attempt}/{max_attempts}). "
                f"Suggested={suggested}s, sleeping {wait:.1f}s…"
            )
            await asyncio.sleep(wait)
    raise RuntimeError("acall_with_backoff: exhausted retries")


# ──────────────────────────────────────────────────────────────────────────────
# Token-aware Groq factory
# ──────────────────────────────────────────────────────────────────────────────

def build_token_aware_groq(model: str, api_key: str, rpm: int, tpm: int,
                           temperature: float = 0.0, max_tokens: int = 1024,
                           timeout: int = 120):
    """Return a ChatGroq subclass instance whose every `_generate` / `_agenerate`
    passes through a sliding-window TPM+RPM limiter AND retries on 429.

    Usage :
        llm = build_token_aware_groq(
            model="openai/gpt-oss-120b",
            api_key=cfg.groq_api_key,
            rpm=30, tpm=8000,
        )
    """
    try:
        from langchain_groq import ChatGroq
    except ImportError as e:
        raise ImportError("`pip install langchain-groq` required.") from e

    limiter = TokenBucketRateLimiter(rpm=rpm, tpm=tpm)
    safety = 0.85
    log.info(
        f"Token-aware Groq : {model} | "
        f"RPM cap={int(rpm * safety)} (limit {rpm}) | "
        f"TPM cap={int(tpm * safety)} (limit {tpm})"
    )

    class TokenAwareGroq(ChatGroq):
        """ChatGroq with adaptive TPM/RPM token bucket + 429 backoff."""

        def _generate(self, messages, *, run_manager=None, stop=None, **kwargs):
            # Use ADAPTIVE output estimate instead of full max_tokens cap.
            # The limiter learns from past calls and refines this.
            input_est = estimate_tokens(messages)
            output_est = limiter.expected_output_tokens()
            est = input_est + output_est
            reserved = limiter.acquire(est)
            result = call_with_backoff(
                super()._generate,
                messages, run_manager=run_manager, stop=stop, **kwargs,
            )
            # Report ACTUAL usage so the limiter releases over-reserved tokens
            # and refines its estimate for the next call.
            total, output = extract_token_usage(result)
            if total > 0:
                limiter.report_actual_tokens(reserved, total, output_only=output)
            return result

        async def _agenerate(self, messages, *, run_manager=None, stop=None, **kwargs):
            input_est = estimate_tokens(messages)
            output_est = limiter.expected_output_tokens()
            est = input_est + output_est
            reserved = await limiter.aacquire(est)
            result = await acall_with_backoff(
                super()._agenerate,
                messages, run_manager=run_manager, stop=stop, **kwargs,
            )
            total, output = extract_token_usage(result)
            if total > 0:
                limiter.report_actual_tokens(reserved, total, output_only=output)
            return result

    return TokenAwareGroq(
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def build_token_aware_gemini(model: str, api_key: str, rpm: int, tpm: int = 0,
                             temperature: float = 0.0, max_output_tokens: int = 1024,
                             timeout: int = 120):
    """Token-aware Gemini wrapper.

    Gemini free tier has RPM limits but no advertised TPM, so `tpm=0` disables
    TPM tracking by default. Also emulates n>1 by sequential calls because lite
    variants reject candidate_count>1.
    """
    try:
        from langchain_core.outputs import ChatResult
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:
        raise ImportError("`pip install langchain-google-genai` required.") from e

    limiter = TokenBucketRateLimiter(rpm=rpm, tpm=tpm)
    log.info(
        f"Token-aware Gemini : {model} | "
        f"RPM cap={int(rpm * 0.85)} (limit {rpm}) | "
        f"TPM tracking={'on' if tpm > 0 else 'off'}"
    )

    class TokenAwareGemini(ChatGoogleGenerativeAI):
        """Gemini wrapper : RPM/TPM limiter + n>1 emulation + 429 backoff."""

        def _generate(self, messages, *, run_manager=None, stop=None, **kwargs):
            n = kwargs.pop("n", None) or 1
            est_per_call = estimate_tokens(messages) + int(
                kwargs.get("max_output_tokens") or max_output_tokens
            )
            limiter.acquire(est_per_call)
            first = call_with_backoff(
                super()._generate, messages, run_manager=run_manager, stop=stop, **kwargs,
            )
            if n == 1:
                return first
            gens = list(first.generations)
            for _ in range(n - 1):
                limiter.acquire(est_per_call)
                more = call_with_backoff(
                    super()._generate, messages, run_manager=run_manager, stop=stop, **kwargs,
                )
                gens.extend(more.generations)
            return ChatResult(generations=gens, llm_output=first.llm_output)

        async def _agenerate(self, messages, *, run_manager=None, stop=None, **kwargs):
            n = kwargs.pop("n", None) or 1
            est_per_call = estimate_tokens(messages) + int(
                kwargs.get("max_output_tokens") or max_output_tokens
            )
            await limiter.aacquire(est_per_call)
            first = await acall_with_backoff(
                super()._agenerate, messages, run_manager=run_manager, stop=stop, **kwargs,
            )
            if n == 1:
                return first
            gens = list(first.generations)
            for _ in range(n - 1):
                await limiter.aacquire(est_per_call)
                more = await acall_with_backoff(
                    super()._agenerate, messages, run_manager=run_manager, stop=stop, **kwargs,
                )
                gens.extend(more.generations)
            return ChatResult(generations=gens, llm_output=first.llm_output)

    return TokenAwareGemini(
        model=model,
        google_api_key=api_key,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout=timeout,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Multi-key rotating Groq factory  (handles TPD exhaustion)
# ──────────────────────────────────────────────────────────────────────────────

def _smart_retry_call(fn, *args, max_attempts: int = 4, base_wait: float = 5.0,
                      max_wait: float = 90.0, **kwargs):
    """Like call_with_backoff but PROPAGATES TPD errors immediately so the
    caller can rotate the API key instead of waiting in vain."""
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            if is_tpd_error(e):
                raise          # propagate for key rotation
            if not is_rate_limit_error(e) or attempt == max_attempts:
                raise
            suggested = parse_retry_after(str(e))
            backoff = min(max_wait, base_wait * (2 ** (attempt - 1)))
            wait = max(suggested + 1.5 if suggested else 0.0, backoff)
            wait += random.uniform(0.5, 2.0)
            log.warning(
                f"TPM 429 (attempt {attempt}/{max_attempts}). "
                f"Suggested={suggested}s, sleeping {wait:.1f}s…"
            )
            time.sleep(wait)
    raise RuntimeError("_smart_retry_call: exhausted retries")


async def _asmart_retry_call(fn, *args, max_attempts: int = 4, base_wait: float = 5.0,
                             max_wait: float = 90.0, **kwargs):
    """Async equivalent of `_smart_retry_call`."""
    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            if is_tpd_error(e):
                raise
            if not is_rate_limit_error(e) or attempt == max_attempts:
                raise
            suggested = parse_retry_after(str(e))
            backoff = min(max_wait, base_wait * (2 ** (attempt - 1)))
            wait = max(suggested + 1.5 if suggested else 0.0, backoff)
            wait += random.uniform(0.5, 2.0)
            log.warning(
                f"TPM 429 (attempt {attempt}/{max_attempts}). "
                f"Suggested={suggested}s, sleeping {wait:.1f}s…"
            )
            await asyncio.sleep(wait)
    raise RuntimeError("_asmart_retry_call: exhausted retries")


def build_rotating_groq(model: str, api_keys: list[str], rpm: int, tpm: int,
                        temperature: float = 0.0, max_tokens: int = 1024,
                        timeout: int = 120):
    """Groq client with TPM limiter + automatic API key rotation on TPD 429.

    When a request fails with a 'tokens per day' (TPD) 429 error, the client
    rotates to the next key in `api_keys` (in order). Each underlying ChatGroq
    instance is rebuilt on rotation so the Groq HTTP client carries the new key.

    Raises RuntimeError when all keys are exhausted.

    Args:
        api_keys: ordered list of Groq API keys (different accounts).
                  The first key is used first; rotation walks down the list.
        rpm, tpm: per-key rate limits (these reset every minute on the active key).

    Usage :
        llm = build_rotating_groq(
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            api_keys=["gsk_key1", "gsk_key2", "gsk_key3"],
            rpm=30, tpm=30000,
        )
    """
    try:
        from langchain_groq import ChatGroq
    except ImportError as e:
        raise ImportError("`pip install langchain-groq` required.") from e

    keys = [k.strip() for k in api_keys if k and k.strip()]
    if not keys:
        raise ValueError("build_rotating_groq: api_keys must contain at least one key")

    # Mutable rotation state (shared by sync + async paths)
    state = {"idx": 0, "exhausted": set()}
    state_lock = threading.Lock()
    limiter = TokenBucketRateLimiter(rpm=rpm, tpm=tpm)
    safety = 0.85
    log.info(
        f"Rotating Groq client : {model} | "
        f"keys={len(keys)} | RPM cap={int(rpm * safety)} | TPM cap={int(tpm * safety)}"
    )

    def _make_inner(key: str):
        """Build a throwaway ChatGroq instance to harvest its initialized
        sync+async HTTP clients (carries the api_key in headers)."""
        return ChatGroq(
            model=model,
            api_key=key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    class RotatingGroq(ChatGroq):
        """ChatGroq with TPM limiter + TPD-driven key rotation."""

        def _rotate(self) -> bool:
            """Mark current key as exhausted, switch to next available.
            Returns False if no key remains."""
            with state_lock:
                state["exhausted"].add(state["idx"])
                for i in range(len(keys)):
                    if i in state["exhausted"]:
                        continue
                    state["idx"] = i
                    inner = _make_inner(keys[i])
                    # Replace HTTP clients in-place (Pydantic field mutation OK
                    # because ChatGroq doesn't freeze fields after init).
                    try:
                        self.client = inner.client
                        self.async_client = inner.async_client
                    except Exception as e:  # noqa: BLE001
                        log.error(f"Could not mutate client after rotation: {e}")
                        return False
                    log.warning(
                        f"🔄 Groq key rotated → key #{i + 1}/{len(keys)} "
                        f"({len(state['exhausted'])} now exhausted)"
                    )
                    return True
                log.error(
                    f"❌ All {len(keys)} Groq keys exhausted (TPD). "
                    "Cannot continue this run — wait 24h or add more keys."
                )
                return False

        def _generate(self, messages, *, run_manager=None, stop=None, **kwargs):
            # Adaptive output estimation : start at default_output_budget,
            # converge to a sliding average of real observed outputs.
            input_est = estimate_tokens(messages)
            output_est = limiter.expected_output_tokens()
            est = input_est + output_est

            # +1 attempt so we still try with the LAST rotated-to key
            for _ in range(len(keys) + 1):
                reserved = limiter.acquire(est)
                try:
                    result = _smart_retry_call(
                        super()._generate, messages,
                        run_manager=run_manager, stop=stop, **kwargs,
                    )
                    # Feed the actual usage back to the limiter
                    total, output = extract_token_usage(result)
                    if total > 0:
                        limiter.report_actual_tokens(reserved, total, output_only=output)
                    return result
                except Exception as e:  # noqa: BLE001
                    if is_tpd_error(e):
                        log.warning(
                            f"⚠️ Key #{state['idx'] + 1}/{len(keys)} exhausted "
                            f"(TPD). Rotating…"
                        )
                        if not self._rotate():
                            raise
                        continue
                    raise
            raise RuntimeError("RotatingGroq: ran out of rotation attempts")

        async def _agenerate(self, messages, *, run_manager=None, stop=None, **kwargs):
            input_est = estimate_tokens(messages)
            output_est = limiter.expected_output_tokens()
            est = input_est + output_est

            for _ in range(len(keys) + 1):
                reserved = await limiter.aacquire(est)
                try:
                    result = await _asmart_retry_call(
                        super()._agenerate, messages,
                        run_manager=run_manager, stop=stop, **kwargs,
                    )
                    total, output = extract_token_usage(result)
                    if total > 0:
                        limiter.report_actual_tokens(reserved, total, output_only=output)
                    return result
                except Exception as e:  # noqa: BLE001
                    if is_tpd_error(e):
                        log.warning(
                            f"⚠️ Key #{state['idx'] + 1}/{len(keys)} exhausted "
                            f"(TPD). Rotating…"
                        )
                        if not self._rotate():
                            raise
                        continue
                    raise
            raise RuntimeError("RotatingGroq: ran out of rotation attempts")

    return RotatingGroq(
        model=model,
        api_key=keys[0],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )


def parse_groq_keys(single_key: str = "", multi_keys: str = "") -> list[str]:
    """Merge the legacy single key and the new comma-separated list into one ordered list."""
    out: list[str] = []
    if multi_keys:
        out.extend(k.strip() for k in multi_keys.split(",") if k.strip())
    if single_key and single_key.strip() and single_key.strip() not in out:
        out.append(single_key.strip())
    return out
