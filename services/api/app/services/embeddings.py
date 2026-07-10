"""Embedding providers for semantic memory.

Three interchangeable providers behind one function so the rest of the codebase
never cares which is active:

- ``local`` (default): a deterministic, dependency-free lexical embedding. It
  hashes token unigrams/bigrams and character trigrams into a fixed-width
  vector and applies a small trading-domain synonym map so morphological
  variants and known synonyms ("fvg" ↔ "fair value gap") land near each other.
  It is NOT a neural embedding — it captures lexical/synonym overlap, not deep
  semantics — but it makes the whole retrieval pipeline runnable offline and in
  hermetic tests. Set ``EMBEDDING_PROVIDER=ollama`` for true semantics.
- ``ollama``: local neural embeddings via an Ollama server (honors the
  local-first thesis; nothing leaves the machine).
- ``openai``: cloud embeddings for users who opt in.

All providers return an L2-normalized ``list[float]`` of length
``settings.embedding_dim`` (or ``None`` when the provider is unreachable, so
ingestion degrades to keyword search rather than failing).
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("app.embeddings")

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Small curated synonym map: each phrase on the right is folded onto the same
# canonical token(s) on the left so the local embedder treats them as related.
# This is deliberately trading-domain specific and intentionally short; it is a
# pragmatic bridge, not a substitute for real embeddings.
_SYNONYMS: dict[str, str] = {
    "fvg": "fair value gap",
    "fair value gap": "fair value gap imbalance",
    "imbalance": "fair value gap imbalance",
    "ob": "order block",
    "order block": "order block supply demand zone",
    "liquidity sweep": "liquidity sweep stop hunt raid",
    "stop hunt": "liquidity sweep stop hunt raid",
    "liquidity grab": "liquidity sweep stop hunt raid",
    "orb": "opening range breakout",
    "opening range breakout": "opening range breakout orb",
    "vwap": "volume weighted average price vwap",
    "s/r": "support resistance level",
    "support resistance": "support resistance level",
    "ny session": "new york session",
    "london open": "london session open",
    "smc": "smart money concepts",
    "bos": "break of structure",
    "choch": "change of character",
}


def embed_text(text: str) -> list[float] | None:
    """Return a normalized embedding for ``text``, or ``None`` on failure."""
    cleaned = (text or "").strip()
    if not cleaned:
        return None
    provider = settings.embedding_provider
    if provider == "local":
        return _local_embed(cleaned)
    if provider == "ollama":
        return _ollama_embed(cleaned) or _local_embed(cleaned)
    if provider == "openai":
        return _openai_embed(cleaned) or _local_embed(cleaned)
    logger.warning("unknown embedding provider '%s'; falling back to local", provider)
    return _local_embed(cleaned)


def embed_batch(texts: list[str]) -> list[list[float] | None]:
    return [embed_text(text) for text in texts]


def cosine_similarity(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    # Providers already L2-normalize, but guard against unnormalized inputs.
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


# --- local provider --------------------------------------------------------


def _expand_synonyms(text: str) -> str:
    lowered = text.lower()
    additions: list[str] = []
    for phrase, expansion in _SYNONYMS.items():
        if phrase in lowered:
            additions.append(expansion)
    if additions:
        return lowered + " " + " ".join(additions)
    return lowered


def _features(text: str) -> list[str]:
    expanded = _expand_synonyms(text)
    tokens = _TOKEN_RE.findall(expanded)
    features: list[str] = list(tokens)
    # Token bigrams capture short phrases ("order block").
    features.extend(f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False))
    # Character trigrams over each token capture morphology ("sweep"/"sweeps").
    for token in tokens:
        if len(token) >= 4:
            padded = f"#{token}#"
            features.extend(padded[i : i + 3] for i in range(len(padded) - 2))
    return features


def _local_embed(text: str) -> list[float]:
    dim = settings.embedding_dim
    vector = [0.0] * dim
    for feature in _features(text):
        digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


# --- ollama provider -------------------------------------------------------


def _ollama_embed(text: str) -> list[float] | None:
    url = f"{settings.ollama_base_url.rstrip('/')}/api/embeddings"
    body = json.dumps({"model": settings.embedding_model, "prompt": text}).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=settings.ai_request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError) as exc:
        logger.warning("ollama embedding failed: %s", exc)
        return None
    return _normalize(payload.get("embedding"))


# --- openai provider -------------------------------------------------------


def _openai_embed(text: str) -> list[float] | None:
    if not settings.openai_api_key:
        return None
    url = "https://api.openai.com/v1/embeddings"
    body = json.dumps({"model": settings.embedding_model, "input": text}).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.openai_api_key}",
        },
    )
    try:
        with urlopen(request, timeout=settings.ai_request_timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return _normalize(payload["data"][0]["embedding"])
    except (HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
        logger.warning("openai embedding failed: %s", exc)
        return None


def _normalize(raw: object) -> list[float] | None:
    if not isinstance(raw, list) or not raw:
        return None
    try:
        vector = [float(value) for value in raw]
    except (TypeError, ValueError):
        return None
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return None
    return [value / norm for value in vector]
