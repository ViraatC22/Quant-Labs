import mimetypes
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Annotated
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_user_id
from app.db.session import get_db
from app.models.domain import JournalEntry, SourceDocument
from app.schemas.vault import (
    AiProviderSelfTest,
    AiRouterStatus,
    AiSelfTestResult,
    JournalEntryCreate,
    JournalEntryRead,
    JournalEntryUpdate,
    SourceDocumentCreate,
    SourceDocumentRead,
    SourceDocumentUpdate,
    StrategyInfo,
    VaultImportRead,
    VaultUrlImportRequest,
)
from app.services.ai_router import (
    active_provider_status,
    extract_strategy_with_ai,
    provider_status,
    router_mode,
    self_test_providers,
)
from app.services.safe_fetch import SsrfError, safe_urlopen
from app.services.source_learning import delete_source_learning, learn_from_source_document
from app.services.technical_extraction import (
    extract_technical_profile,
    extract_technical_tags,
    is_technical_tag,
    technical_tags_from_profile,
)

router = APIRouter()

MAX_IMPORT_BYTES = 1_500_000
MAX_BODY_CHARS = 96_000
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
    "risk parity": "risk-parity",
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
    ("risk parity", "Risk parity"),
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

ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
ARXIV_CATEGORY_LABELS = {
    "q-fin.CP": "Computational Finance",
    "q-fin.EC": "Economics",
    "q-fin.GN": "General Finance",
    "q-fin.MF": "Mathematical Finance",
    "q-fin.PM": "Portfolio Management",
    "q-fin.PR": "Pricing of Securities",
    "q-fin.RM": "Risk Management",
    "q-fin.ST": "Statistical Finance",
    "q-fin.TR": "Trading and Market Microstructure",
}


@dataclass(frozen=True)
class ArxivMetadata:
    arxiv_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    submitted: str | None = None
    updated: str | None = None
    comments: str | None = None
    doi: str | None = None
    primary_category: str | None = None
    categories: list[str] = field(default_factory=list)
    abs_url: str | None = None
    pdf_url: str | None = None


# Tags whose text is site chrome, not content.
_BOILERPLATE_TAGS = {
    "script", "style", "noscript", "svg", "nav", "header", "footer", "aside",
    "form", "button", "figure", "select", "option", "label",
}
# class/id/role substrings that mark navigation/boilerplate regions.
_BOILERPLATE_HINTS = (
    "nav", "menu", "sidebar", "footer", "header", "breadcrumb", "masthead",
    "banner", "cookie", "subscribe", "newsletter", "comment", "related",
    "promo", "advert", "social", "search", "toolbar", "site-",
)
# class/id substrings that mark the primary content region.
_MAIN_HINTS = (
    "mw-parser-output", "article-body", "article__body", "post-content",
    "entry-content", "story-body", "post-body", "content__body",
)
_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input", "link",
    "meta", "param", "source", "track", "wbr",
}


class _HTMLTextExtractor(HTMLParser):
    """Extract readable article text, skipping nav/boilerplate.

    Maintains a tag stack; text in a boilerplate region (nav/header/footer or an
    element whose class/id/role hints at chrome) is dropped. If a main-content
    region (<main>/<article> or a known content class) is seen, only text inside
    it is kept; otherwise all non-boilerplate text is kept as a fallback.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.description = ""
        self._in_title = False
        self._stack: list[dict] = []
        self._main_parts: list[str] = []
        self._all_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): (value or "") for key, value in attrs}
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            name = attr_map.get("name", "").lower()
            prop = attr_map.get("property", "").lower()
            if (name == "description" or prop == "og:description") and not self.description:
                self.description = attr_map.get("content", "").strip()
        if tag in _VOID_TAGS:
            return
        ident = f"{attr_map.get('class', '')} {attr_map.get('id', '')} {attr_map.get('role', '')}".lower()
        is_skip = tag in _BOILERPLATE_TAGS or any(hint in ident for hint in _BOILERPLATE_HINTS)
        is_main = tag in {"main", "article"} or any(hint in ident for hint in _MAIN_HINTS)
        self._stack.append({"tag": tag, "skip": is_skip, "main": is_main})

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in _VOID_TAGS:
            return
        for index in range(len(self._stack) - 1, -1, -1):
            if self._stack[index]["tag"] == tag:
                del self._stack[index:]
                break

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title = f"{self.title} {text}".strip()
            return
        if any(frame["skip"] for frame in self._stack):
            return
        self._all_parts.append(text)
        if any(frame["main"] for frame in self._stack):
            self._main_parts.append(text)

    @property
    def text(self) -> str:
        parts = self._main_parts if self._main_parts else self._all_parts
        return _clean_text(" ".join(parts))


class _ArxivAbsExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_text = ""
        self.authors_text = ""
        self.abstract = ""
        self.dateline = ""
        self.subjects_text = ""
        self.comments = ""
        self.doi = ""
        self.pdf_url = ""
        self._capture: str | None = None
        self._skip_descriptor = 0
        self._parts: dict[str, list[str]] = {
            "title": [],
            "authors": [],
            "abstract": [],
            "dateline": [],
            "subjects": [],
            "comments": [],
        }

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        class_name = attr_map.get("class", "")
        href = attr_map.get("href", "")

        if tag == "span" and "descriptor" in class_name:
            self._skip_descriptor += 1
        if tag == "h1" and "title" in class_name:
            self._capture = "title"
        elif tag == "div" and "authors" in class_name:
            self._capture = "authors"
        elif tag == "blockquote" and "abstract" in class_name:
            self._capture = "abstract"
        elif tag == "div" and "dateline" in class_name:
            self._capture = "dateline"
        elif tag == "td" and "subjects" in class_name:
            self._capture = "subjects"
        elif tag == "td" and "comments" in class_name:
            self._capture = "comments"

        if href:
            if "/pdf/" in href and not self.pdf_url:
                self.pdf_url = href
            if "doi.org/" in href and not self.doi:
                self.doi = href.removeprefix("https://doi.org/").removeprefix("http://doi.org/")

    def handle_endtag(self, tag: str) -> None:
        if tag == "span" and self._skip_descriptor:
            self._skip_descriptor -= 1
        if tag in {"h1", "div", "blockquote", "td"}:
            self._capture = None

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text or not self._capture or self._skip_descriptor:
            return
        self._parts[self._capture].append(text)

    def close(self) -> None:
        super().close()
        self.title_text = _clean_text(" ".join(self._parts["title"])).removeprefix("Title:")
        self.authors_text = _clean_text(" ".join(self._parts["authors"])).removeprefix("Authors:")
        self.abstract = _clean_text(" ".join(self._parts["abstract"])).removeprefix("Abstract:")
        self.dateline = _clean_text(" ".join(self._parts["dateline"]))
        self.subjects_text = _clean_text(" ".join(self._parts["subjects"]))
        self.comments = _clean_text(" ".join(self._parts["comments"]))


def _clean_text(value: str) -> str:
    # Strip citation/edit markers common in wiki/article text ([2], [ 8 ],
    # [edit], [citation needed]) so they don't leak into rules and summaries.
    value = re.sub(r"\[\s*(?:\d+|edit|citation needed)\s*\]", "", value, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", value).strip()


def _date_label(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        return value[:10]


def _arxiv_dateline_date(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"Submitted on\s+(\d{1,2}\s+[A-Za-z]{3}\s+\d{4})", value)
    if not match:
        return None
    try:
        return datetime.strptime(match.group(1), "%d %b %Y").date().isoformat()
    except ValueError:
        return match.group(1)


def _decode_bytes(raw: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([\w.-]+)", content_type, re.IGNORECASE)
    charset = charset_match.group(1) if charset_match else "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except LookupError:
        return raw.decode("utf-8", errors="replace")


def _arxiv_id_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    if host not in {"arxiv.org", "export.arxiv.org"}:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2 or parts[0] not in {"abs", "pdf"}:
        return None

    candidate = parts[1].removesuffix(".pdf")
    candidate = re.sub(r"v\d+$", "", candidate)
    if re.fullmatch(r"\d{4}\.\d{4,5}", candidate) or re.fullmatch(
        r"[a-z.-]+/\d{7}", candidate,
        re.IGNORECASE,
    ):
        return candidate
    return None


def _fetch_arxiv_metadata(arxiv_id: str) -> ArxivMetadata:
    api_url = f"https://export.arxiv.org/api/query?id_list={quote(arxiv_id)}"
    request = Request(
        api_url,
        headers={"User-Agent": "QuantLabsVaultImporter/0.1 (+local-first research vault)"},
    )
    try:
        with urlopen(request, timeout=10) as response:
            raw = response.read(MAX_IMPORT_BYTES)
        return _parse_arxiv_atom(raw, arxiv_id)
    except (ET.ParseError, HTTPError, URLError, TimeoutError, ValueError):
        return _fetch_arxiv_abs_metadata(arxiv_id)


def _fetch_arxiv_abs_metadata(arxiv_id: str) -> ArxivMetadata:
    abs_url = f"https://arxiv.org/abs/{quote(arxiv_id)}"
    request = Request(
        abs_url,
        headers={"User-Agent": "QuantLabsVaultImporter/0.1 (+local-first research vault)"},
    )
    with urlopen(request, timeout=10) as response:
        raw = response.read(MAX_IMPORT_BYTES)
        content_type = response.headers.get("content-type", "text/html")
    return _parse_arxiv_abs_html(raw, arxiv_id, content_type=content_type)


def _parse_arxiv_subjects(value: str) -> tuple[str | None, list[str]]:
    categories: list[str] = []
    for match in re.finditer(r"\(([a-z.-]+\.[A-Z]{2})\)", value):
        categories.append(match.group(1))
    categories = list(dict.fromkeys(categories))
    return (categories[0] if categories else None, categories)


def _parse_arxiv_abs_html(
    raw: bytes,
    fallback_id: str,
    *,
    content_type: str = "text/html",
) -> ArxivMetadata:
    parser = _ArxivAbsExtractor()
    parser.feed(_decode_bytes(raw, content_type))
    parser.close()

    title = _clean_text(parser.title_text).removeprefix("Title:").strip()
    if not title:
        raise ValueError(f"No arXiv title found for {fallback_id}.")

    authors = [
        author.strip(" ,")
        for author in re.split(r"\s*,\s*|\s+and\s+", parser.authors_text)
        if author.strip(" ,")
    ]
    primary, categories = _parse_arxiv_subjects(parser.subjects_text)
    pdf_url = parser.pdf_url
    if pdf_url.startswith("/"):
        pdf_url = f"https://arxiv.org{pdf_url}"

    return ArxivMetadata(
        arxiv_id=fallback_id,
        title=title,
        authors=authors,
        abstract=_clean_text(parser.abstract),
        submitted=_arxiv_dateline_date(parser.dateline),
        updated=None,
        comments=parser.comments or None,
        doi=parser.doi or None,
        primary_category=primary,
        categories=categories,
        abs_url=f"https://arxiv.org/abs/{fallback_id}",
        pdf_url=pdf_url or f"https://arxiv.org/pdf/{fallback_id}",
    )


def _parse_arxiv_atom(raw: bytes, fallback_id: str) -> ArxivMetadata:
    root = ET.fromstring(raw)
    entry = root.find(f"{ATOM_NS}entry")
    if entry is None:
        raise ValueError(f"No arXiv record found for {fallback_id}.")

    title = _clean_text(entry.findtext(f"{ATOM_NS}title") or fallback_id)
    abstract = _clean_text(entry.findtext(f"{ATOM_NS}summary") or "")
    authors = [
        _clean_text(author.findtext(f"{ATOM_NS}name") or "")
        for author in entry.findall(f"{ATOM_NS}author")
    ]
    authors = [author for author in authors if author]
    categories = [
        category.attrib["term"]
        for category in entry.findall(f"{ATOM_NS}category")
        if category.attrib.get("term")
    ]
    primary = entry.find(f"{ARXIV_NS}primary_category")
    links = entry.findall(f"{ATOM_NS}link")
    pdf_url = next(
        (
            link.attrib.get("href")
            for link in links
            if link.attrib.get("title") == "pdf" or link.attrib.get("type") == "application/pdf"
        ),
        None,
    )

    return ArxivMetadata(
        arxiv_id=fallback_id,
        title=title,
        authors=authors,
        abstract=abstract,
        submitted=_date_label(entry.findtext(f"{ATOM_NS}published")),
        updated=_date_label(entry.findtext(f"{ATOM_NS}updated")),
        comments=_clean_text(entry.findtext(f"{ARXIV_NS}comment") or "") or None,
        doi=_clean_text(entry.findtext(f"{ARXIV_NS}doi") or "") or None,
        primary_category=primary.attrib.get("term") if primary is not None else None,
        categories=categories,
        abs_url=_clean_text(entry.findtext(f"{ATOM_NS}id") or "") or None,
        pdf_url=pdf_url,
    )


def _arxiv_subjects(metadata: ArxivMetadata) -> list[str]:
    labels: list[str] = []
    for category in metadata.categories or [metadata.primary_category or ""]:
        if not category:
            continue
        label = ARXIV_CATEGORY_LABELS.get(category, category)
        labels.append(f"{label} ({category})" if label != category else category)
    return list(dict.fromkeys(labels))


def _arxiv_implementation_notes(metadata: ArxivMetadata) -> list[str]:
    text = f"{metadata.title}. {metadata.abstract}"
    sentences = _sentences(text)
    title_key = metadata.title.strip(". ").lower()
    needles = {
        "strategy",
        "strategies",
        "signal",
        "signals",
        "estimator",
        "portfolio",
        "optimization",
        "drift",
        "feedback",
        "trading",
        "ema",
        "macd",
    }
    notes = [
        _excerpt(sentence)
        for sentence in sentences
        if sentence.strip(". ").lower() != title_key
        and any(_sentence_has_needle(sentence, needle) for needle in needles)
    ]
    if notes:
        return notes[:4]
    return [_excerpt(sentence) for sentence in sentences[:2]]


def _arxiv_details(metadata: ArxivMetadata, source: str) -> dict:
    return {
        "provider": "arxiv",
        "arxiv_id": metadata.arxiv_id,
        "title": metadata.title,
        "authors": metadata.authors,
        "abstract": metadata.abstract,
        "submitted": metadata.submitted,
        "updated": metadata.updated,
        "comments": metadata.comments,
        "doi": metadata.doi,
        "primary_category": metadata.primary_category,
        "subjects": _arxiv_subjects(metadata),
        "abs_url": metadata.abs_url or f"https://arxiv.org/abs/{metadata.arxiv_id}",
        "pdf_url": metadata.pdf_url or source,
        "implementation_notes": _arxiv_implementation_notes(metadata),
    }


def _arxiv_body(metadata: ArxivMetadata) -> str:
    subjects = _arxiv_subjects(metadata)
    parts = [
        f"Title: {metadata.title}",
        f"Authors: {', '.join(metadata.authors) if metadata.authors else 'Unknown'}",
        f"Submitted: {metadata.submitted or 'Unknown'}",
    ]
    if subjects:
        parts.append(f"Subjects: {', '.join(subjects)}")
    if metadata.abstract:
        parts.append(f"Abstract: {metadata.abstract}")
    if metadata.comments:
        parts.append(f"Comments: {metadata.comments}")
    if metadata.doi:
        parts.append(f"DOI: {metadata.doi}")

    notes = _arxiv_implementation_notes(metadata)
    if notes:
        parts.append("Strategy implementation notes:\n- " + "\n- ".join(notes))
    return "\n\n".join(parts)[:MAX_BODY_CHARS]


def _arxiv_import(source: str) -> VaultImportRead | None:
    arxiv_id = _arxiv_id_from_url(source)
    if not arxiv_id:
        return None

    metadata = _fetch_arxiv_metadata(arxiv_id)
    details = _arxiv_details(metadata, source)
    subject_tags = [
        category.lower().replace(".", "-")
        for category in [metadata.primary_category, *metadata.categories]
        if category
    ]
    imported = _enriched_import(
        title=metadata.title[:240],
        kind="paper",
        source=source,
        body=_arxiv_body(metadata),
        metadata={
            "content_type": "application/arxiv+atom",
            "import_method": "arxiv",
            "source_details": details,
            "tags": sorted({"paper", "arxiv", *subject_tags}),
            "abs_url": details["abs_url"],
            "pdf_url": details["pdf_url"],
        },
    )
    extra_tags = set(imported.metadata.get("tags", []))
    imported.tags = sorted({*imported.tags, *extra_tags})
    imported.metadata["tags"] = imported.tags
    return imported


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


# Tags with no trading signal that keyword matching tends to over-produce.
_NOISE_TAGS = {"trade", "journal", "paper", "article", "note", "strategy", "backtest"}
MAX_TAGS = 14


def _is_noise_tag(tag: str) -> bool:
    # Drop domain-style tags (e.g. en.wikipedia.org) and generic meta words.
    return "." in tag or tag in _NOISE_TAGS


def _clean_tags(tags: set[str] | list[str], *, limit: int = MAX_TAGS) -> list[str]:
    cleaned = sorted(
        {tag.strip().lower() for tag in tags if tag and tag.strip() and not _is_noise_tag(tag.strip().lower())}
    )
    return cleaned[:limit]


def _metadata_tags(title: str, body: str, source: str, kind: str) -> list[str]:
    tags = [kind]
    tags.extend(_keyword_tags(f"{title} {body[:4000]}"))
    tags.extend(technical_tags_from_profile(extract_technical_profile(f"{title} {body[:9000]}")))
    return sorted({tag for tag in tags if tag})


def _sentences(text: str) -> list[str]:
    chunks = re.split(r"(?<=[.!?])\s+|\n+|(?:^|\s)[-*]\s+", text)
    sentences = [_clean_text(chunk).strip(" -") for chunk in chunks]
    return [sentence for sentence in sentences if len(sentence) >= 8]


def _strategy_sentence(sentence: str) -> str | None:
    if re.match(r"^(?:Title|Authors|Submitted|Subjects|Comments|DOI):", sentence, re.IGNORECASE):
        return None
    cleaned = re.sub(r"^(?:Abstract|Summary):\s*", "", sentence, flags=re.IGNORECASE)
    cleaned = _clean_text(cleaned)
    return cleaned or None


def _rules_from_sentences(sentences: list[str], needles: set[str], limit: int = 3) -> list[str]:
    matches: list[str] = []
    for sentence in sentences:
        strategy_sentence = _strategy_sentence(sentence)
        if not strategy_sentence:
            continue
        if any(_sentence_has_needle(strategy_sentence, needle) for needle in needles):
            rule = _excerpt(strategy_sentence, 160)
            if rule not in matches:
                matches.append(rule)
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
        strategy_sentence = _strategy_sentence(sentence)
        if strategy_sentence and len(strategy_sentence) >= 24:
            return strategy_sentence[:260]
    return f"Generated strategy context for {title}."


def _excerpt(value: str, limit: int = 220) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit].rsplit(' ', 1)[0]}..."


def _sentence_has_needle(sentence: str, needle: str) -> bool:
    lowered = sentence.lower()
    if " " in needle:
        return needle in lowered
    return re.search(rf"\b{re.escape(needle)}\b", lowered, re.IGNORECASE) is not None


def _ai_tags(title: str, body: str, source: str, kind: str) -> list[str]:
    text = f"{title} {source} {body[:6000]}"
    tags = set(_keyword_tags(text))
    tags.update(technical_tags_from_profile(extract_technical_profile(text)))
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
    technical_profile = extract_technical_profile(text)
    technical_tags = technical_tags_from_profile(technical_profile)
    setup = _first_setup(text)
    indicators = sorted({*_indicators(text), *technical_profile.get("indicators", [])})
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
            bool(technical_tags),
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
        technical_tags=technical_tags,
        technical_profile=technical_profile,
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
    local_technical_profile = extract_technical_profile(f"{title} {body[:9000]}")
    local_technical_tags = technical_tags_from_profile(local_technical_profile)
    base_tags = _metadata_tags(title, body, source, kind)
    generated_tags = _ai_tags(title, body, source, kind)
    source_tags = {
        str(tag).strip()
        for tag in metadata.get("tags", [])
        if str(tag).strip()
    }
    strategy_info = _strategy_info(title, body, kind)
    ai_extraction = extract_strategy_with_ai(title=title, kind=kind, source=source, body=body)
    enriched_title = ai_extraction.title if ai_extraction and ai_extraction.title else title
    if ai_extraction:
        generated_tags = sorted({*generated_tags, *ai_extraction.tags})
        strategy_info = ai_extraction.strategy_info or strategy_info
        if strategy_info:
            local_profile = extract_technical_profile(f"{enriched_title} {body[:9000]}")
            merged_profile = {
                **local_profile,
                **{
                    key: sorted({*local_profile.get(key, []), *values})
                    for key, values in strategy_info.technical_profile.items()
                },
            }
            strategy_info.technical_profile = merged_profile
            strategy_info.technical_tags = sorted(
                {*strategy_info.technical_tags, *technical_tags_from_profile(merged_profile)}
            )
            generated_tags = sorted({*generated_tags, *strategy_info.technical_tags})

    technical_tags = strategy_info.technical_tags if strategy_info else local_technical_tags
    technical_profile = (
        strategy_info.technical_profile if strategy_info else local_technical_profile
    )

    generated_tags = _clean_tags(generated_tags)
    technical_tags = _clean_tags(technical_tags)
    all_tags = _clean_tags({*base_tags, *generated_tags, *source_tags})

    metadata = {
        **metadata,
        "generated_tags": generated_tags,
        "technical_tags": technical_tags,
        "technical_profile": technical_profile,
        "enrichment_method": "ai_router" if ai_extraction else "local_semantic_rules",
        "ai_router": {
            "mode": router_mode(),
            "provider": ai_extraction.provider_id if ai_extraction else None,
            "model": ai_extraction.model if ai_extraction else None,
        },
    }
    if strategy_info:
        strategy_info.technical_tags = technical_tags
        metadata["strategy_info"] = strategy_info.model_dump()

    return VaultImportRead(
        title=enriched_title[:240],
        kind=kind,
        source=source,
        body=body,
        tags=all_tags,
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


def _source_url_for_document(document: SourceDocument) -> str:
    metadata = document.source_metadata or {}
    source = document.uri or str(metadata.get("source", ""))
    return source.strip()


def _document_needs_supported_refresh(document: SourceDocument) -> bool:
    source = _source_url_for_document(document)
    if not _arxiv_id_from_url(source):
        return False

    metadata = document.source_metadata or {}
    source_details = metadata.get("source_details")
    if not isinstance(source_details, dict) or source_details.get("provider") != "arxiv":
        return True

    title_is_placeholder = document.title == _fallback_title(source)
    body_is_placeholder = (document.content_text or "").startswith("Uploaded pdf file:")
    return title_is_placeholder or body_is_placeholder or _has_noisy_strategy_metadata(metadata)


def _has_noisy_strategy_metadata(metadata: dict) -> bool:
    strategy_info = metadata.get("strategyInfo") or metadata.get("strategy_info")
    if not isinstance(strategy_info, dict):
        return False
    summary = str(strategy_info.get("summary", ""))
    if summary.startswith(("Title:", "Authors:", "Submitted:", "Subjects:")):
        return True
    if summary.lower().startswith(("presented at ", "accepted at ", "submitted to ")):
        return True
    for key in ["entry_rules", "exit_rules", "risk_rules"]:
        values = strategy_info.get(key)
        if not isinstance(values, list):
            continue
        for value in values:
            text = str(value)
            if "Abstract:" in text or text.startswith(("Authors:", "Submitted:", "Subjects:")):
                return True
    return False


def _apply_import_to_document(document: SourceDocument, imported: VaultImportRead) -> None:
    old_metadata = document.source_metadata or {}
    strategy_dump = imported.strategy_info.model_dump() if imported.strategy_info else None
    metadata = {
        **old_metadata,
        **imported.metadata,
        "source": imported.source,
        "tags": imported.tags,
        "aiTags": imported.ai_tags,
        "generated_tags": imported.ai_tags,
        "sourceDetails": imported.metadata.get("source_details")
        or old_metadata.get("sourceDetails"),
        "technicalTags": imported.metadata.get("technical_tags", []),
        "technicalProfile": imported.metadata.get("technical_profile", {}),
        "strategy_info": strategy_dump,
        "strategyInfo": strategy_dump,
    }

    document.title = imported.title
    document.document_type = imported.kind
    document.uri = imported.source if imported.source.startswith("http") else document.uri
    document.content_text = imported.body
    document.source_metadata = metadata


def _refresh_document_if_supported(
    db: Session,
    *,
    document: SourceDocument,
    user_id: UUID,
) -> bool:
    if not _document_needs_supported_refresh(document):
        return False

    try:
        imported = _arxiv_import(_source_url_for_document(document))
    except (ET.ParseError, HTTPError, URLError, TimeoutError, ValueError):
        return False

    if imported is None:
        return False

    delete_source_learning(db, document_id=document.id, user_id=user_id)
    _apply_import_to_document(document, imported)
    db.flush()
    learn_from_source_document(db, document=document, user_id=user_id)
    return True


def _document_read(document: SourceDocument) -> SourceDocumentRead:
    metadata = _document_metadata(document)
    return SourceDocumentRead(
        id=document.id,
        title=document.title,
        document_type=document.document_type,
        uri=document.uri,
        content_text=document.content_text,
        metadata=metadata,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def _document_metadata(document: SourceDocument) -> dict:
    metadata = dict(document.source_metadata or {})
    text = " ".join([document.title, document.document_type, document.content_text or ""])
    profile = metadata.get("technical_profile")
    if not isinstance(profile, dict) or not profile:
        profile = extract_technical_profile(text)

    tags = {
        str(tag).strip().lower()
        for tag in metadata.get("technical_tags", [])
        if str(tag).strip()
    }
    tags.update(extract_technical_tags(text))
    tags.update(
        str(tag).strip().lower()
        for tag in metadata.get("tags", [])
        if str(tag).strip() and is_technical_tag(str(tag))
    )

    if profile:
        metadata["technical_profile"] = profile
        metadata["technicalProfile"] = profile
    if tags:
        metadata["technical_tags"] = sorted(tags)
        metadata["technicalTags"] = sorted(tags)
    if isinstance(metadata.get("source_details"), dict):
        metadata["sourceDetails"] = metadata["source_details"]

    strategy_info = metadata.get("strategyInfo") or metadata.get("strategy_info")
    if isinstance(strategy_info, dict) and (profile or tags):
        enriched_strategy = dict(strategy_info)
        enriched_strategy.setdefault("technical_profile", profile)
        enriched_strategy["technical_tags"] = sorted(
            {
                *[
                    str(tag).strip().lower()
                    for tag in enriched_strategy.get("technical_tags", [])
                    if str(tag).strip()
                ],
                *tags,
            }
        )
        if "strategyInfo" in metadata:
            metadata["strategyInfo"] = enriched_strategy
        metadata["strategy_info"] = enriched_strategy

    return metadata


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


@router.get("/ai/providers", response_model=AiRouterStatus)
def ai_provider_status() -> AiRouterStatus:
    active = active_provider_status()
    return AiRouterStatus(
        mode=router_mode(),
        active_provider_id=active.id if active else None,
        providers=provider_status(),
    )


@router.get("/ai/providers/self-test", response_model=AiSelfTestResult)
def ai_provider_self_test() -> AiSelfTestResult:
    """Canary each configured provider so misconfiguration is visible."""
    return AiSelfTestResult(
        mode=router_mode(),
        providers=[AiProviderSelfTest(**result) for result in self_test_providers()],
    )


@router.post("/import-url", response_model=VaultImportRead)
def import_url(payload: VaultUrlImportRequest) -> VaultImportRead:
    parsed = urlparse(payload.url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL must start with http:// or https://.",
        )

    try:
        arxiv_import = _arxiv_import(payload.url)
    except (ET.ParseError, HTTPError, URLError, TimeoutError, ValueError):
        arxiv_import = None
    if arxiv_import:
        return arxiv_import

    try:
        with safe_urlopen(
            payload.url,
            timeout=10,
            headers={"User-Agent": "QuantLabsVaultImporter/0.1 (+local-first research vault)"},
        ) as response:
            content_type = response.headers.get("content-type", "application/octet-stream")
            raw = response.read(MAX_IMPORT_BYTES + 1)
    except SsrfError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
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
    if _document_needs_supported_refresh(document):
        try:
            imported = _arxiv_import(_source_url_for_document(document))
        except (ET.ParseError, HTTPError, URLError, TimeoutError, ValueError):
            imported = None
        if imported:
            _apply_import_to_document(document, imported)

    db.add(document)
    db.flush()
    learn_from_source_document(db, document=document, user_id=user_id)
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
    refreshed = [
        _refresh_document_if_supported(db, document=document, user_id=user_id)
        for document in documents
    ]
    if any(refreshed):
        db.commit()
        for document in documents:
            db.refresh(document)
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
    limit: Annotated[int | None, Query(ge=1, le=1000)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[JournalEntryRead]:
    query = (
        select(JournalEntry)
        .where(JournalEntry.user_id == user_id)
        .order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc())
        .offset(offset)
    )
    if limit is not None:
        query = query.limit(limit)
    entries = db.scalars(query).all()
    return [_journal_read(entry) for entry in entries]


@router.patch("/documents/{document_id}", response_model=SourceDocumentRead)
def update_document(
    document_id: UUID,
    payload: SourceDocumentUpdate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> SourceDocumentRead:
    document = db.get(SourceDocument, document_id)
    if document is None or document.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    fields = payload.model_fields_set
    content_changed = False
    if "title" in fields and payload.title is not None:
        document.title = payload.title
        content_changed = True
    if "document_type" in fields and payload.document_type is not None:
        document.document_type = payload.document_type
        content_changed = True
    if "content_text" in fields:
        document.content_text = payload.content_text
        content_changed = True
    if "metadata" in fields and payload.metadata is not None:
        document.source_metadata = {**(document.source_metadata or {}), **payload.metadata}

    # Re-learn so memory chunks and graph nodes reflect the edited content
    # instead of drifting from it. IDs are preserved (edit, not delete+create).
    if content_changed:
        delete_source_learning(db, document_id=document.id, user_id=user_id)
        db.flush()
        learn_from_source_document(db, document=document, user_id=user_id)

    db.commit()
    db.refresh(document)
    return _document_read(document)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:
    document = db.get(SourceDocument, document_id)
    if document is None or document.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    delete_source_learning(db, document_id=document.id, user_id=user_id)
    db.delete(document)
    db.commit()


@router.patch("/journal-entries/{entry_id}", response_model=JournalEntryRead)
def update_journal_entry(
    entry_id: UUID,
    payload: JournalEntryUpdate,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> JournalEntryRead:
    entry = db.get(JournalEntry, entry_id)
    if entry is None or entry.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found."
        )

    fields = payload.model_fields_set
    if "entry_date" in fields and payload.entry_date is not None:
        entry.entry_date = payload.entry_date
    if "title" in fields and payload.title is not None:
        entry.title = payload.title
    if "body" in fields and payload.body is not None:
        entry.body = payload.body
    if "emotional_state" in fields:
        entry.emotional_state = payload.emotional_state
    if "tags" in fields and payload.tags is not None:
        entry.tags = payload.tags
    if "metadata" in fields and payload.metadata is not None:
        entry.journal_metadata = {**(entry.journal_metadata or {}), **payload.metadata}

    db.commit()
    db.refresh(entry)
    return _journal_read(entry)


@router.delete("/journal-entries/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_journal_entry(
    entry_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    user_id: Annotated[UUID, Depends(get_current_user_id)],
) -> None:
    entry = db.get(JournalEntry, entry_id)
    if entry is None or entry.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Journal entry not found."
        )
    db.delete(entry)
    db.commit()
