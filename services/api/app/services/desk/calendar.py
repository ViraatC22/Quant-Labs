"""Economic calendar via the ForexFactory weekly XML feed.

Chosen over FMP/Finnhub/Trading Economics because it is free, needs no key, and
carries the field those paid tiers gate: the **consensus forecast**. Impact
tiers (High/Medium/Low/Holiday) come with it, which is what the calendar UI
grades events by.

Two things about this source are load-bearing and easy to get wrong:

* **Timestamps are UTC.** Verified against five known release times — ECB 14:15
  CEST arrives as ``12:15pm``, UK CPI 07:00 BST as ``6:00am``, Canadian CPI
  08:30 EDT as ``12:30pm``, AU jobs 11:30 AEST as ``1:30am``. Treating these as
  local time would misplace every event on the timeline by hours.
* **The payload is windows-1252, not UTF-8.** Decoding it as UTF-8 mangles
  names like "Vujčić", so the declared encoding is honoured explicitly.

Only the current week is published; ``nextweek``/``lastweek`` variants 404. The
feed is an unofficial CDN endpoint, so it is cached hard and degrades to an
explicit "unavailable" state rather than inventing events.
"""

from __future__ import annotations

import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError

from app.core.logging import get_logger
from app.services.safe_fetch import SsrfError, safe_urlopen

logger = get_logger("app.desk.calendar")

FEED_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"

# The feed refreshes actual values as releases print, so a short TTL keeps the
# "actual" column current without hammering an endpoint we do not own.
CALENDAR_CACHE_TTL_SECONDS = 900.0
CALENDAR_STALE_MAX_SECONDS = 21_600.0

_REQUEST_TIMEOUT = 12.0
_MAX_BYTES = 2_000_000

IMPACT_HIGH = "high"
IMPACT_MEDIUM = "medium"
IMPACT_LOW = "low"
IMPACT_HOLIDAY = "holiday"
IMPACT_UNKNOWN = "unknown"

_IMPACT_MAP = {
    "high": IMPACT_HIGH,
    "medium": IMPACT_MEDIUM,
    "low": IMPACT_LOW,
    "holiday": IMPACT_HOLIDAY,
}

# Non-clock time values the feed uses instead of a timestamp.
_ALL_DAY = {"all day", "allday"}
_TENTATIVE = {"tentative", "tbd"}

_cache: tuple[list[CalendarEvent], float] | None = None
_cache_lock = threading.Lock()


@dataclass(frozen=True)
class CalendarEvent:
    title: str
    currency: str
    impact: str
    # None for all-day or tentative events, which have a date but no time.
    scheduled_at: datetime | None
    date_label: str
    all_day: bool
    tentative: bool
    forecast: str | None
    previous: str | None
    actual: str | None
    url: str | None

    @property
    def is_high_impact(self) -> bool:
        return self.impact == IMPACT_HIGH


@dataclass(frozen=True)
class CalendarFeed:
    events: tuple[CalendarEvent, ...]
    available: bool
    stale: bool = False
    reason: str | None = None
    source: str = "forexfactory"


def _text(node: ET.Element, tag: str) -> str | None:
    value = node.findtext(tag)
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _parse_datetime(date_text: str, time_text: str | None) -> tuple[datetime | None, bool, bool]:
    """Return ``(utc_datetime, all_day, tentative)`` for one event.

    The feed's date is ``MM-DD-YYYY`` and its time is a 12-hour clock. Both are
    UTC (see module docstring).
    """
    lowered = (time_text or "").strip().lower()
    all_day = lowered in _ALL_DAY
    tentative = lowered in _TENTATIVE

    try:
        day = datetime.strptime(date_text, "%m-%d-%Y").replace(tzinfo=UTC)
    except ValueError:
        return None, all_day, tentative

    if all_day or tentative or not lowered:
        return None, all_day, tentative

    for fmt in ("%I:%M%p", "%I%p"):
        try:
            parsed = datetime.strptime(lowered.replace(" ", ""), fmt)
        except ValueError:
            continue
        return (
            day.replace(hour=parsed.hour, minute=parsed.minute),
            False,
            False,
        )

    # An unrecognized time is reported as an undated event for that day rather
    # than guessed at — a wrong hour on a calendar is worse than a missing one.
    logger.info("unrecognized calendar time %r; treating as undated", time_text)
    return None, all_day, tentative


def _event_from_node(node: ET.Element) -> CalendarEvent | None:
    title = _text(node, "title")
    date_text = _text(node, "date")
    if not title or not date_text:
        return None

    time_text = _text(node, "time")
    scheduled_at, all_day, tentative = _parse_datetime(date_text, time_text)
    raw_impact = (_text(node, "impact") or "").lower()

    return CalendarEvent(
        title=title,
        currency=(_text(node, "country") or "").upper() or "—",
        impact=_IMPACT_MAP.get(raw_impact, IMPACT_UNKNOWN),
        scheduled_at=scheduled_at,
        date_label=date_text,
        all_day=all_day,
        tentative=tentative,
        forecast=_text(node, "forecast"),
        previous=_text(node, "previous"),
        actual=_text(node, "actual"),
        url=_text(node, "url"),
    )


def _fetch_from_provider() -> list[CalendarEvent]:
    with safe_urlopen(
        FEED_URL,
        timeout=_REQUEST_TIMEOUT,
        headers={"User-Agent": "QuantLabsDesk/0.1 (+local-first trading journal)"},
    ) as response:
        raw = response.read(_MAX_BYTES)

    # Honour the declared encoding; the feed is windows-1252.
    root = ET.fromstring(raw.decode("windows-1252", errors="replace"))
    parsed = (_event_from_node(node) for node in root.findall("event"))
    events = [event for event in parsed if event is not None]
    # Undated events sort after timed ones.
    far_future = datetime.max.replace(tzinfo=UTC)
    events.sort(key=lambda e: (e.scheduled_at is None, e.scheduled_at or far_future))
    return events


def fetch_calendar() -> CalendarFeed:
    """Return this week's events, or an empty feed explaining why not."""
    global _cache
    now = time.monotonic()
    with _cache_lock:
        cached = _cache
    if cached and now - cached[1] < CALENDAR_CACHE_TTL_SECONDS:
        return CalendarFeed(events=tuple(cached[0]), available=True)

    try:
        events = _fetch_from_provider()
    except (
        HTTPError,
        URLError,
        SsrfError,
        TimeoutError,
        ValueError,
        OSError,
        ET.ParseError,
    ) as exc:
        if cached and now - cached[1] < CALENDAR_STALE_MAX_SECONDS:
            logger.warning("calendar provider failed; serving stale cache: %s", exc)
            return CalendarFeed(
                events=tuple(cached[0]),
                available=True,
                stale=True,
                reason="Showing a cached calendar; the provider is unreachable.",
            )
        logger.warning("calendar provider failed with no cache: %s", exc)
        return CalendarFeed(
            events=(),
            available=False,
            reason=f"The economic calendar is unavailable ({type(exc).__name__}).",
        )

    with _cache_lock:
        _cache = (events, time.monotonic())
    return CalendarFeed(events=tuple(events), available=True)
