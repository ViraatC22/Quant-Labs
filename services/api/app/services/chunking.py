"""Boundary-aware overlapping text chunking.

Replaces the old fixed 1600-char whitespace slicer. Chunks respect sentence and
paragraph boundaries where possible, target ~1000 characters, and overlap by a
configurable ratio so a fact spanning a boundary is retrievable from either
side. Token counts are estimated (~4 chars/token) rather than word counts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TARGET_CHARS = 1000
OVERLAP_RATIO = 0.15
MAX_CHARS = 1600

# Split on paragraph breaks first, then sentence terminators. Keeping the
# terminator with the sentence avoids gluing "London." onto the next sentence.
_PARAGRAPH_RE = re.compile(r"\n\s*\n")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


@dataclass(frozen=True)
class Chunk:
    text: str
    token_count: int


def estimate_tokens(text: str) -> int:
    """Rough token estimate. ~4 chars/token is a reasonable English heuristic."""
    return max(1, round(len(text) / 4))


def _segments(text: str) -> list[str]:
    segments: list[str] = []
    for paragraph in _PARAGRAPH_RE.split(text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        for sentence in _SENTENCE_RE.split(paragraph):
            sentence = sentence.strip()
            if sentence:
                segments.append(sentence)
    return segments


def _hard_split(segment: str) -> list[str]:
    """A single segment longer than MAX_CHARS (e.g. a table) is sliced."""
    return [segment[i : i + MAX_CHARS].strip() for i in range(0, len(segment), MAX_CHARS)]


def chunk_text(text: str) -> list[Chunk]:
    """Split ``text`` into overlapping, boundary-aware chunks."""
    normalized = (text or "").strip()
    if not normalized:
        return []

    segments: list[str] = []
    for segment in _segments(normalized):
        if len(segment) > MAX_CHARS:
            segments.extend(_hard_split(segment))
        else:
            segments.append(segment)
    if not segments:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for segment in segments:
        seg_len = len(segment) + 1
        if current and current_len + seg_len > TARGET_CHARS:
            chunks.append(" ".join(current))
            # Carry the tail of the finished chunk into the next one so
            # boundary-spanning facts survive in both.
            current = _overlap_tail(current)
            current_len = sum(len(part) + 1 for part in current)
        current.append(segment)
        current_len += seg_len
    if current:
        chunks.append(" ".join(current))

    return [
        Chunk(text=chunk, token_count=estimate_tokens(chunk))
        for chunk in chunks
        if chunk.strip()
    ]


def _overlap_tail(segments: list[str]) -> list[str]:
    """Return the trailing segments that fit within the overlap budget."""
    budget = int(TARGET_CHARS * OVERLAP_RATIO)
    tail: list[str] = []
    total = 0
    for segment in reversed(segments):
        total += len(segment) + 1
        if total > budget and tail:
            break
        tail.insert(0, segment)
        if total > budget:
            break
    return tail
