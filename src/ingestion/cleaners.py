"""Light-weight text normalization."""
from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"[ \t]+")
_MULTIPLE_NEWLINES = re.compile(r"\n{3,}")
# Unpaired surrogates (U+D800..U+DFFF) — illegal in UTF-8.
# Common in PDFs that mis-encode mathematical symbols.
_SURROGATE_RE = re.compile(r"[\ud800-\udfff]")
# Other control chars that pollute extracted PDF text
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(text: str) -> str:
    """
    Conservative cleanup :
      - strip unpaired Unicode surrogates and control chars (PDF garbage)
      - Unicode NFKC normalization
      - collapse runs of spaces / tabs
      - cap consecutive newlines at 2
      - strip leading/trailing whitespace
    Avoids destructive lowercasing or punctuation stripping (kills RAG quality).
    """
    if not text:
        return ""
    text = _SURROGATE_RE.sub("", text)
    text = _CONTROL_RE.sub("", text)
    text = unicodedata.normalize("NFKC", text)
    text = _WHITESPACE_RE.sub(" ", text)
    text = _MULTIPLE_NEWLINES.sub("\n\n", text)
    return text.strip()
