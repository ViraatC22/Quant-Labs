import mimetypes
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import JournalEntry, SourceDocument
from app.schemas.vault import (
    JournalEntryCreate,
    JournalEntryRead,
    SourceDocumentCreate,
    SourceDocumentRead,
    StrategyInfo,
    VaultImportRead,
    VaultUrlImportRequest,
)

router = APIRouter()

MAX_IMPORT_BYTES = 1_500_000
MAX_BODY_CHARS = 24_000
TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".log", ".pine", ".py"}
KEYWORD_TAGS = {
    "atr",
    "orb",
    "vwap",
    "ema",
    "sma",
    "rsi",
    "macd",
    "breakout",
    "breakdown",
    "pullback",
    "reversal",
    "momentum",
    "scalp",
    "swing",
    "volume",
    "liquidity",
    "support",
    "resistance",
    "trend",
    "risk",
    "strategy",
    "trade",
    "journal",
    "backtest",
    "paper",
    "loss",
    "setup",
    "entry",
    "exit",
    "stop",
    "target",
    "earnings",
    "fomc",
    "options",
    "futures",
    "crypto",
}

PHRASE_TAGS = {
    "opening range": "orb",
    "opening range breakout": "orb",
    "mean reversion": "mean-reversion",
    "trend following": "trend-following",
    "range break": "range-break",
    "gap up": "gap",
    "gap down": "gap",
    "stop loss": "stop-loss",
    "take profit": "take-profit",
    "risk reward": "risk-reward",
    "position size": "position-sizing",
}

SETUP_PATTERNS = [
    ("opening range breakout", "Opening range breakout"),
    ("opening range", "Opening range breakout"),
    ("orb", "Opening range breakout"),
    ("vwap pullback", "VWAP pullback"),
    ("pullback", "Pullback continuation"),
    ("mean reversion", "Mean reversion"),
    ("trend following", "Trend following"),
    ("breakout", "Breakout continuation"),
    ("breakdown", "Breakdown continuation"),
    ("reversal", "Reversal"),
]

INDICATOR_PATTERNS = {
    "vwap": "VWAP",
    "ema": "EMA",
    "sma": "SMA",
    "rsi": "RSI",
    "macd": "MACD",
    "atr": "ATR",
    "volume": "Volume",
}

MARKET_PATTERNS = [
    ("futures", "futures"),
    ("options", "options"),
    ("crypto", "crypto"),
    ("forex", "forex"),
    ("equity", "equities"),
    ("stock", "equities"),
    ("spy", "equities"),
    ("qqq", "equities"),
    ("es", "futures"),
    ("nq", "futures"),
]

TIMEFRAME_PATTERNS = [
    r"\b(?:1|2|3|5|10|15|30|60)[ -]?(?:m|min|minute|minutes)\b",
    r"\b(?:1|2|4)[ -]?(?:h|hr|hour|hours)\b",
    r"\b(?:daily|weekly|monthly|intraday|premarket|pre-market)\b",
]


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.description = ""
        self._in_title = False
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            attr_map = {key.lower(): value or "" for key, value in attrs}
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            if name == "description" or prop == "og:description":
                self.description = attr_map.get("content", "").strip()

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
            return
        if not self._skip_depth:
            self._parts.append(text)

    @property
    def text(self) -> str:
        return _clean_text(" ".join(self._parts))


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _decode_bytes(raw: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([\w.-]+)", content_type, re.IGNORECASE)
    charset = charset_match.group(1) if charset_match else "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _domain_tag(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host.split(":")[0] or "link"


def _infer_kind(source: str, content_type: str) -> str:
    suffix = Path(urlparse(source).path or source).suffix.lower()
    normalized_type = content_type.split(";")[0].lower()
    if normalized_type == "text/html":
        return "article"
    if normalized_type == "application/pdf" or suffix == ".pdf":
        return "pdf"
    if normalized_type.startswith("image/"):
        return "screenshot"
    if suffix == ".csv":
        return "broker_import"
    if suffix in {".pine", ".py"}:
        return "strategy"
    return "note"


def _keyword_tags(text: str) -> list[str]:
    lowered = text.lower()
    tags = {
        tag
        for tag in KEYWORD_TAGS
        if re.search(rf"\b{re.escape(tag)}\b", lowered, re.IGNORECASE)
    }
    tags.update(tag for phrase, tag in PHRASE_TAGS.items() if phrase in lowered)
    return sorted(tags)


def _metadata_tags(title: str, body: str, source: str, kind: str) -> list[str]:
    tags = [kind]
    if source.startswith("http"):
        tags.append(_domain_tag(source))
    tags.extend(_keyword_tags(f"{title} {body[:4000]}"))
    return sorted({tag for tag in tags if tag})


def _sentences(text: str) -> list[str]:
    compact = _clean_text(text)
    chunks = re.split(r"(?<=[.!?])\s+|\n+|(?:^|\s)[-*]\s+", compact)
    return [chunk.strip(" -") for chunk in chunks if len(chunk.strip(" -")) >= 8]


def _rules_from_sentences(sentences: list[str], needles: set[str], limit: int = 3) -> list[str]:
    matches: list[str] = []
    for sentence in sentences:
        lowered = sentence.lower()
        if any(needle in lowered for needle in needles):
            matches.append(sentence[:220])
        if len(matches) == limit:
            break
    return matches


def _first_timeframe(text: str) -> str | None:
    for pattern in TIMEFRAME_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).upper().replace("MINUTE", "min").replace("MINUTES", "min")
    return None


def _first_setup(text: str) -> str | None:
    lowered = text.lower()
    for phrase, label in SETUP_PATTERNS:
        if phrase in lowered:
            return label
    return None


def _first_market(text: str) -> str | None:
    lowered = text.lower()
    for phrase, label in MARKET_PATTERNS:
        if re.search(rf"\b{re.escape(phrase)}\b", lowered, re.IGNORECASE):
            return label
    return None


def _indicators(text: str) -> list[str]:
    return sorted(
        {
            label
            for phrase, label in INDICATOR_PATTERNS.items()
            if re.search(rf"\b{re.escape(phrase)}\b", text, re.IGNORECASE)
        }
    )


def _summary(title: str, body: str) -> str:
    for sentence in _sentences(body):
        if len(sentence) >= 24:
            return sentence[:260]
    return f"Generated strategy context for {title}."


def _ai_tags(title: str, body: str, source: str, kind: str) -> list[str]:
    text = f"{title} {source} {body[:6000]}"
    tags = set(_keyword_tags(text))
    setup = _first_setup(text)
    market = _first_market(text)
    timeframe = _first_timeframe(text)
    if setup:
        tags.add(setup.lower().replace(" ", "-"))
    if market:
        tags.add(market)
    if timeframe:
        tags.add("timeframe")
    if kind in {"strategy", "broker_import"}:
        tags.add(kind)
    tags.update(indicator.lower() for indicator in _indicators(text))
    return sorted(tag for tag in tags if tag)


def _strategy_info(title: str, body: str, kind: str) -> StrategyInfo | None:
    text = f"{title}\n{body[:9000]}"
    sentences = _sentences(text)
    setup = _first_setup(text)
    indicators = _indicators(text)
    timeframe = _first_timeframe(text)
    market = _first_market(text)
    entry_rules = _rules_from_sentences(
        sentences,
        {"entry", "enter", "buy", "long", "short", "trigger", "break", "reclaim", "confirmation"},
    )
    exit_rules = _rules_from_sentences(
        sentences,
        {"exit", "target", "take profit", "profit", "sell", "cover", "trail"},
    )
    risk_rules = _rules_from_sentences(
        sentences,
        {"risk", "stop", "invalidation", "max loss", "position size", "size", "atr"},
    )
    signal_count = sum(
        [
            bool(setup),
            bool(indicators),
            bool(timeframe),
            bool(market),
            bool(entry_rules),
            bool(exit_rules),
            bool(risk_rules),
            kind == "strategy",
            "strategy" in text.lower(),
        ]
    )
    if signal_count < 2:
        return None

    confidence = min(0.95, 0.25 + signal_count * 0.08)
    return StrategyInfo(
        name=title,
        summary=_summary(title, body),
        setup=setup,
        entry_rules=entry_rules,
        exit_rules=exit_rules,
        risk_rules=risk_rules,
        timeframe=timeframe,
        indicators=indicators,
        market=market,
        confidence=round(confidence, 2),
    )


def _enriched_import(
    *,
    title: str,
    kind: str,
    source: str,
    body: str,
    metadata: dict,
) -> VaultImportRead:
    base_tags = _metadata_tags(title, body, source, kind)
    generated_tags = _ai_tags(title, body, source, kind)
    strategy_info = _strategy_info(title, body, kind)
    metadata = {
        **metadata,
        "generated_tags": generated_tags,
        "enrichment_method": "local_semantic_rules",
    }
    if strategy_info:
        metadata["strategy_info"] = strategy_info.model_dump()

    return VaultImportRead(
        title=title[:240],
        kind=kind,
        source=source,
        body=body,
        tags=sorted({*base_tags, *generated_tags}),
        ai_tags=generated_tags,
        strategy_info=strategy_info,
        metadata=metadata,
    )


def _fallback_title(source: str) -> str:
    parsed = urlparse(source)
    if parsed.netloc:
        path_name = Path(parsed.path).stem.replace("-", " ").replace("_", " ").strip()
        return path_name.title() or parsed.netloc.removeprefix("www.")
    return Path(source).stem.replace("-", " ").replace("_", " ").strip().title() or source


def _html_import(raw: bytes, source: str, content_type: str) -> VaultImportRead:
    parser = _HTMLTextExtractor()
    parser.feed(_decode_bytes(raw, content_type))
    body_parts = [part for part in [parser.description, parser.text] if part]
    body = "\n\n".join(body_parts)[:MAX_BODY_CHARS]
    title = _clean_text(parser.title) or _fallback_title(source)
    kind = _infer_kind(source, content_type)
    return _enriched_import(
        title=title[:240],
        kind=kind,
        source=source,
        body=body or f"Imported {source}",
        metadata={"content_type": content_type, "import_method": "url"},
    )


def _bytes_import(raw: bytes, source: str, content_type: str) -> VaultImportRead:
    kind = _infer_kind(source, content_type)
    title = _fallback_title(source)
    if kind in {"note", "strategy", "broker_import"} or content_type.startswith("text/"):
        body = _decode_bytes(raw, content_type)[:MAX_BODY_CHARS]
    else:
        size_kb = max(1, round(len(raw) / 1024))
        body = (
            f"Uploaded {kind} file: {source} ({size_kb} KB). "
            "Text extraction is queued for a later parser."
        )

    return _enriched_import(
        title=title[:240],
        kind=kind,
        source=source,
        body=body,
        metadata={
            "content_type": content_type or "application/octet-stream",
            "byte_count": len(raw),
            "import_method": "file" if not source.startswith("http") else "url",
        },
    )


def _import_bytes(raw: bytes, source: str, content_type: str) -> VaultImportRead:
    normalized_type = content_type.split(";")[0].lower()
    if normalized_type == "text/html":
        return _html_import(raw, source, content_type)
    return _bytes_import(raw, source, content_type)


def _document_read(document: SourceDocument) -> SourceDocumentRead:
    return SourceDocumentRead(
        id=document.id,
        title=document.title,
        document_type=document.document_type,
        uri=document.uri,
        content_text=document.content_text,
        metadata=document.source_metadata,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _journal_read(entry: JournalEntry) -> JournalEntryRead:
    return JournalEntryRead(
        id=entry.id,
        entry_date=entry.entry_date,
        title=entry.title,
        body=entry.body,
        emotional_state=entry.emotional_state,
        tags=entry.tags,
        metadata=entry.journal_metadata,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


@router.post("/import-url", response_model=VaultImportRead)
def import_url(payload: VaultUrlImportRequest) -> VaultImportRead:
    parsed = urlparse(payload.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http:// or https://.",
        )

    request = Request(
        payload.url,
        headers={"User-Agent": "QuantLabsVaultImporter/0.1 (+local-first research vault)"},
    )

    try:
        with urlopen(request, timeout=10) as response:
            content_type = response.headers.get("content-type", "application/octet-stream")
            raw = response.read(MAX_IMPORT_BYTES + 1)
    except HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not import URL: HTTP {exc.code}.",
        ) from exc
    except URLError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not import URL: {exc.reason}.",
        ) from exc

    if len(raw) > MAX_IMPORT_BYTES:
        raw = raw[:MAX_IMPORT_BYTES]

    return _import_bytes(raw, payload.url, content_type)


@router.post("/import-file", response_model=VaultImportRead)
async def import_file(file: Annotated[UploadFile, File()]) -> VaultImportRead:
    raw = await file.read(MAX_IMPORT_BYTES + 1)
    if len(raw) > MAX_IMPORT_BYTES:
        raw = raw[:MAX_IMPORT_BYTES]

    filename = file.filename or "uploaded-file"
    content_type = (
        file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
    )
    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_EXTENSIONS and content_type == "application/octet-stream":
        content_type = "text/plain"

    return _import_bytes(raw, filename, content_type)


@router.post("/documents", response_model=SourceDocumentRead, status_code=201)
def create_document(
    payload: SourceDocumentCreate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SourceDocumentRead:
    document = SourceDocument(
        user_id=user_id,
        title=payload.title,
        document_type=payload.document_type,
        uri=payload.uri,
        content_text=payload.content_text,
        source_metadata=payload.metadata,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return _document_read(document)


@router.get("/documents", response_model=list[SourceDocumentRead])
def list_documents(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[SourceDocumentRead]:
    documents = db.scalars(
        select(SourceDocument)
        .where(SourceDocument.user_id == user_id)
        .order_by(SourceDocument.created_at.desc())
    ).all()
    return [_document_read(document) for document in documents]


@router.post("/journal-entries", response_model=JournalEntryRead, status_code=201)
def create_journal_entry(
    payload: JournalEntryCreate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> JournalEntryRead:
    entry = JournalEntry(
        user_id=user_id,
        entry_date=payload.entry_date,
        title=payload.title,
        body=payload.body,
        emotional_state=payload.emotional_state,
        tags=payload.tags,
        journal_metadata=payload.metadata,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _journal_read(entry)


@router.get("/journal-entries", response_model=list[JournalEntryRead])
def list_journal_entries(
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> list[JournalEntryRead]:
    entries = db.scalars(
        select(JournalEntry)
        .where(JournalEntry.user_id == user_id)
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
    ).all()
    return [_journal_read(entry) for entry in entries]
