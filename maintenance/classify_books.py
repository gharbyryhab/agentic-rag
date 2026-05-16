"""
Classification automatique des livres via extraction intelligente de la ToC.

Usage:
    python -m maintenance.classify_books
    python -m maintenance.classify_books --limit 5
    python -m maintenance.classify_books --force
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from src.llm.gemini_client import GeminiClient
from src.utils import get_logger

log = get_logger("classify_books")

# ─── Rate Limiter ─────────────────────────────────────────────────────────────

class RateLimiter:
    MAX_RPM = 12
    MIN_DELAY = 60 / MAX_RPM

    def __init__(self):
        self._last_call: float = 0.0
        self._backoff: float = 0.0

    def wait(self):
        elapsed = time.monotonic() - self._last_call
        required = self.MIN_DELAY + self._backoff
        if elapsed < required:
            time.sleep(required - elapsed)
        self._last_call = time.monotonic()

    def on_success(self):
        self._backoff = 0.0

    def on_rate_limited(self, retry_after: float | None = None):
        self._backoff = retry_after + 5 if retry_after else max(self._backoff * 2, 30)
        log.warning(f"429 → backoff {self._backoff:.0f}s")


_rate_limiter = RateLimiter()

# ─── Prompt ───────────────────────────────────────────────────────────────────

CLASSIFY_PROMPT = """
You are a library cataloging expert. Analyze the table of contents and return ONLY a valid JSON object. No markdown, no backticks, no explanation.

Book filename: {filename}

Table of Contents (cleaned):
---
{toc_content}
---

Return exactly this JSON structure:
{{
  "title": "book title extracted from filename or ToC (without author name)",
  "author": "author name(s) only, extracted from filename or ToC",
  "main_domain": "exactly one of: [machine_learning, deep_learning, data_science, mathematics_ml, nlp, generative_ai, general_ai, feature_engineering, reinforcement_learning, python_programming, business_ai, miscellaneous]",
  "detected_domain": "the domain as YOU would naturally describe it, freely, without any constraint on the list above (ex: 'bayesian statistics', 'computer vision', 'MLOps', 'time series analysis'...)",
  "sub_domains": ["relevant", "sub-topics"],
  "level": "exactly one of: [beginner, intermediate, advanced, expert]",
  "target_audience": "short description of target audience",
  "language": "en or fr",
  "pedagogical": true or false,
  "practical": true or false,
  "theoretical": true or false,
  "key_chapters": ["3 to 5 most important chapter titles from the ToC"],
  "description": "2-3 sentences describing the book content and value"
}}
"""

# ─── ToC Detection ────────────────────────────────────────────────────────────

_TOC_KEYWORDS = [
    "table of contents", "contents", "sommaire",
    "table des matières", "table des matieres",
]

_DOT_PATTERN = re.compile(r"\.{3,}|…{2,}|\s{2,}\d{1,4}\s*$", re.MULTILINE)

_TOC_END_KEYWORDS = [
    "preface", "préface", "foreword", "acknowledgment",
    "chapter 1", "chapitre 1", "part i", "partie i",
]

# Patterns de lignes à supprimer de la ToC
_NOISE_PATTERNS = [
    re.compile(r"^\[Page \d+\]$"),                         # [Page 6]
    re.compile(r"^-+$"),                                   # ------
    re.compile(r"^={3,}$"),                                # ======
    re.compile(r"^\d+$"),                                  # chiffres seuls
    re.compile(r"^[ivxlcdmIVXLCDM]+$"),                   # chiffres romains seuls (v, xi...)
    re.compile(r"www\.", re.IGNORECASE),                   # URLs
    re.compile(r"^\s*[■●▪▶►◆]\s*Contents?\s*$", re.IGNORECASE),  # "■ Contents"
    re.compile(r"[\ufffd\u0000-\u0008\u000b\u000e-\u001f]{2,}"),  # caractères corrompus
]

# Mots qui signalent du contenu parasite dans la ToC
_NOISE_WORDS = [
    "i would like", "je remercie", "massachusetts institute",
    "professor of", "bruce tidor", "series foreword",
    "pocket-size", "essential knowledge", "synthesizing",
    "www.it-ebooks", "copyright ©", "isbn ", "published by",
    "all rights reserved", "printed in",
]


def _clean_toc_line(line: str) -> str:
    """Nettoie une ligne de ToC."""
    # Remplacer tabulations
    line = line.replace("\t", " ")
    # Supprimer les séquences de caractères corrompus (ex: ������)
    line = re.sub(r"[\ufffd]{2,}", "", line)
    line = re.sub(r"[\u0000-\u0008\u000b\u000e-\u001f]", "", line)
    # Supprimer les suites de points ou tirets (leaders de ToC)
    line = re.sub(r"[.\u2026]{4,}", " ", line)
    line = re.sub(r"[─═─]{4,}", "", line)
    # Supprimer numéros de page à la fin
    line = re.sub(r"\s+\d{1,4}\s*$", "", line)
    # Supprimer les chiffres romains en début de ligne seuls (v, xi...)
    line = re.sub(r"^[ivxlcdmIVXLCDM]{1,6}\s*$", "", line, flags=re.IGNORECASE)
    # Normaliser espaces
    line = re.sub(r" {2,}", " ", line)
    return line.strip()


def _is_noise_line(line: str) -> bool:
    """Retourne True si la ligne est du bruit."""
    if not line:
        return True

    line_lower = line.lower()

    # Patterns bruit
    for pattern in _NOISE_PATTERNS:
        if pattern.search(line):
            return True

    # Mots bruit
    if any(noise in line_lower for noise in _NOISE_WORDS):
        return True

    # Ligne trop courte (1-2 caractères)
    if len(line) <= 2:
        return True

    # Ligne avec trop de caractères spéciaux (PDF corrompu)
    special_ratio = sum(1 for c in line if ord(c) > 127) / max(len(line), 1)
    if special_ratio > 0.4:
        return True

    return False


def _is_toc_page(text: str) -> bool:
    text_lower = text.lower().strip()
    has_keyword = any(kw in text_lower for kw in _TOC_KEYWORDS)
    has_dot_pattern = len(_DOT_PATTERN.findall(text)) >= 3
    return has_keyword or has_dot_pattern


def _is_toc_end(text: str, toc_pages_collected: int) -> bool:
    if toc_pages_collected == 0:
        return False
    if len(_DOT_PATTERN.findall(text)) >= 2:
        return False
    text_lower = text.lower().strip()
    return any(
        text_lower.startswith(kw) or f"\n{kw}" in text_lower[:200]
        for kw in _TOC_END_KEYWORDS
    )


def extract_toc(pdf_path: Path, max_pages: int = 20) -> tuple[list[str], str]:
    """
    Extrait et nettoie la ToC d'un PDF.
    Returns: (toc_lines_clean, method)
    """
    try:
        reader = PdfReader(str(pdf_path), strict=False)
        total = len(reader.pages)
        scan_limit = min(max_pages, total)

        toc_pages_raw: list[str] = []
        toc_started = False

        for i in range(scan_limit):
            try:
                text = reader.pages[i].extract_text() or ""
            except Exception:
                continue

            if not toc_started:
                if _is_toc_page(text):
                    toc_started = True
                    toc_pages_raw.append(text)
            else:
                if _is_toc_end(text, len(toc_pages_raw)):
                    break
                if len(toc_pages_raw) >= 8:
                    break
                toc_pages_raw.append(text)

        raw_text = "\n".join(toc_pages_raw)
        method = "toc_found" if toc_pages_raw else "fallback_first_pages"

        if not toc_pages_raw:
            log.warning(f"ToC non trouvée → fallback: {pdf_path.name}")
            fallback = []
            for i in range(min(5, total)):
                try:
                    fallback.append(reader.pages[i].extract_text() or "")
                except Exception:
                    continue
            raw_text = "\n".join(fallback)

        # ── Nettoyage ligne par ligne ─────────────────────────────────────────
        clean_lines: list[str] = []
        seen: set[str] = set()  # éviter les doublons

        for raw_line in raw_text.splitlines():
            cleaned = _clean_toc_line(raw_line)

            if not cleaned:
                continue
            if _is_noise_line(cleaned):
                continue
            # Ignorer les titres "Contents", "Sommaire"...
            if any(cleaned.lower() == kw for kw in _TOC_KEYWORDS):
                continue
            # Dédupliquer
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)

            clean_lines.append(cleaned)

        return clean_lines, method

    except (PdfReadError, Exception) as e:
        log.error(f"Erreur lecture PDF {pdf_path.name}: {e}")
        return [], "pdf_error"


# ─── JSON Parsing ─────────────────────────────────────────────────────────────

def _parse_json(response: str) -> dict:
    clean = response.strip()
    if "```" in clean:
        parts = clean.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                clean = part
                break
    if not clean.startswith("{"):
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start != -1 and end > start:
            clean = clean[start:end]
    return json.loads(clean)


# ─── Appel LLM avec retry ────────────────────────────────────────────────────

def _extract_retry_after(err_str: str) -> float | None:
    match = re.search(
        r"retry(?:Delay|[^'\"]*in)[^0-9]*(\d+(?:\.\d+)?)\s*s",
        err_str, re.IGNORECASE
    )
    return float(match.group(1)) if match else None


# Markers of transient server-side errors we want to retry (vs hard failures
# like 400 / 401 / 403 which mean "your request is wrong, retrying won't help").
_TRANSIENT_MARKERS = (
    "500", "502", "503", "504",
    "INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED",
    "ServiceUnavailable", "InternalServerError",
)


def _is_transient(err_str: str) -> bool:
    return any(m in err_str for m in _TRANSIENT_MARKERS)


def _llm_generate_safe(llm: GeminiClient, prompt: str, max_retries: int = 4) -> str:
    for attempt in range(1, max_retries + 1):
        _rate_limiter.wait()
        try:
            result = llm.generate(prompt)
            _rate_limiter.on_success()
            return result
        except Exception as e:
            err_str = str(e)

            # ─── Rate limit (429) : honor server's retryDelay if present ───
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                retry_after = _extract_retry_after(err_str)
                _rate_limiter.on_rate_limited(retry_after)
                if attempt < max_retries:
                    log.warning(f"429 (tentative {attempt}/{max_retries}) → retry...")
                    continue
                raise

            # ─── Transient server errors (5xx) : exponential backoff ───
            if _is_transient(err_str):
                if attempt < max_retries:
                    backoff = 2 ** attempt  # 2s, 4s, 8s, 16s
                    log.warning(
                        f"Transient API error (tentative {attempt}/{max_retries}) "
                        f"→ sleep {backoff}s : {err_str[:120]}"
                    )
                    time.sleep(backoff)
                    continue
                raise

            # ─── Hard failure (4xx other than 429, malformed request, etc.) ───
            raise


# ─── Classification ───────────────────────────────────────────────────────────

def classify_book(llm: GeminiClient, pdf_path: Path) -> dict:
    toc_lines, method = extract_toc(pdf_path)

    base = {
        "folder": pdf_path.parent.name,
        "extraction_method": method,
        "toc_extracted": toc_lines,
    }

    if not toc_lines:
        return {**base, "error": f"Content not extractable ({method})"}

    # Max 40 lignes envoyées au LLM (suffisant pour classifier)
    toc_for_llm = "\n".join(toc_lines[:40])

    prompt = CLASSIFY_PROMPT.format(
        filename=pdf_path.name,
        toc_content=toc_for_llm,
    )

    # Tentative 1
    try:
        response = _llm_generate_safe(llm, prompt)
        result = _parse_json(response)
        return {**base, **result}
    except json.JSONDecodeError:
        log.warning(f"Invalid JSON → retry: {pdf_path.name}")
    except Exception as e:
        return {**base, "error": str(e)}

    # Tentative 2 — prompt strict
    try:
        strict = (
            "Return ONLY a valid JSON object. "
            "Start with { and end with }. No markdown, no text before or after.\n\n"
            + prompt
        )
        response2 = _llm_generate_safe(llm, strict)
        result = _parse_json(response2)
        base["extraction_method"] += "_retry"
        return {**base, **result}
    except Exception:
        return {**base, "error": "Invalid JSON after retry"}


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true",
                        help="Re-classify already processed books")
    args = parser.parse_args()

    data_raw = ROOT / "data" / "raw"
    output_file = ROOT / "results" / "metadata" / "books_metadata.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Charger résultats existants
    existing: dict = {}
    if output_file.exists():
        with open(output_file, "r", encoding="utf-8") as f:
            existing = json.load(f)
        log.info(f"Resuming: {len(existing)} books already classified")

    llm = GeminiClient()

    # Collecte + déduplication
    all_pdfs = list(data_raw.rglob("*.pdf")) + list(data_raw.rglob("*.PDF"))
    seen: dict[str, Path] = {}
    for pdf_path in sorted(all_pdfs):
        key = str(pdf_path.resolve()).lower()
        if key not in seen:
            seen[key] = pdf_path

    pdf_files = list(seen.values())
    duplicates = len(all_pdfs) - len(pdf_files)

    log.info(f"PDFs found     : {len(all_pdfs)}")
    log.info(f"Duplicates     : {duplicates}")
    log.info(f"Unique books   : {len(pdf_files)}")

    if args.limit:
        pdf_files = pdf_files[:args.limit]

    results = dict(existing)
    errors = []

    for i, pdf_path in enumerate(pdf_files, 1):
        key = pdf_path.name  # clé = nom du fichier uniquement

        # Resume only on SUCCESSFUL prior classifications. Errored entries
        # (network failure, invalid JSON, etc.) must be retried, otherwise
        # a network outage permanently corrupts the cache.
        already_ok = key in existing and "error" not in existing[key]
        if already_ok and not args.force:
            log.info(f"[{i}/{len(pdf_files)}] SKIP : {key[:65]}")
            continue

        log.info(f"[{i}/{len(pdf_files)}] → {key[:70]}")

        metadata = classify_book(llm, pdf_path)
        results[key] = metadata

        if "error" in metadata:
            log.error(f"    ERROR : {metadata['error']}")
            errors.append(key)
        else:
            log.info(
                f"    domain  : {metadata.get('main_domain', '?')} | "
                f"level   : {metadata.get('level', '?')} | "
                f"method  : {metadata.get('extraction_method', '?')} | "
                f"toc_lines: {len(metadata.get('toc_extracted', []))}"
            )

        # Sauvegarde après chaque livre
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

    _print_summary(results, errors, output_file)


def _print_summary(results: dict, errors: list, output_file: Path):
    from collections import Counter
    valides = {k: v for k, v in results.items() if "error" not in v}

    print("\n" + "=" * 60)
    print(f"TOTAL     : {len(results)} books")
    print(f"Success   : {len(valides)}")
    print(f"Errors    : {len(errors)}")

    if valides:
        domains  = Counter(v.get("main_domain", "?") for v in valides.values())
        levels   = Counter(v.get("level", "?") for v in valides.values())
        methods  = Counter(v.get("extraction_method", "?") for v in valides.values())

        print("\n── BY DOMAIN ──")
        for d, n in domains.most_common():
            print(f"  {d:<35} {n} books")

        print("\n── BY LEVEL ──")
        for lvl, count in levels.most_common():
            print(f"  {lvl:<20} {count} books")

        print("\n── EXTRACTION METHOD ──")
        for m, count in methods.most_common():
            print(f"  {m:<30} {count} books")

    print(f"\nResults → {output_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()