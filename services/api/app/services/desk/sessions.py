"""Market session phases and countdowns to the next transition.

Drives the session strip ("LONDON · OPEN · closes in 1h 58m"). Everything here
is pure: given an instant, it computes the phase and the next boundary from
declared trading hours. No network, no clock reads inside the logic — `now` is
always passed in — so the weekend and DST edges are actually testable.

DST is handled by resolving wall-clock times in each venue's own zone via
`zoneinfo`, never by adding fixed UTC offsets. London and New York shift on
different dates, so a hardcoded offset is wrong for several weeks a year.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

PRE_MARKET = "pre_market"
OPEN = "open"
AFTER_HOURS = "after_hours"
CLOSED = "closed"

PHASE_LABELS = {
    PRE_MARKET: "Pre-market",
    OPEN: "Open",
    AFTER_HOURS: "After hours",
    CLOSED: "Closed",
}

# How far to scan for the surrounding boundaries. Four days covers a Friday
# close through a Monday open with room to spare.
_SEARCH_DAYS = 5


@dataclass(frozen=True)
class MarketSession:
    """Declared trading hours for one venue, in that venue's local wall clock."""

    key: str
    label: str
    timezone: str
    regular_open: time
    regular_close: time
    pre_market_open: time | None = None
    after_hours_close: time | None = None
    trading_days: tuple[int, ...] = (0, 1, 2, 3, 4)  # Mon-Fri
    # True when the session opens on one calendar day and closes on the next
    # (CME Globex: 18:00 ET → 17:00 ET). `trading_days` then lists the days the
    # session *opens*, not the days it covers.
    overnight: bool = False

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


# Equity venues carry pre/post sessions; FX centres are modelled as the liquidity
# window traders actually refer to, which is why they have no pre-market phase.
SESSIONS: tuple[MarketSession, ...] = (
    MarketSession(
        key="london",
        label="London",
        timezone="Europe/London",
        pre_market_open=time(5, 5),
        regular_open=time(8, 0),
        regular_close=time(16, 30),
    ),
    MarketSession(
        key="new_york",
        label="New York",
        timezone="America/New_York",
        pre_market_open=time(4, 0),
        regular_open=time(9, 30),
        regular_close=time(16, 0),
        after_hours_close=time(20, 0),
    ),
    MarketSession(
        key="sydney",
        label="Sydney",
        timezone="Australia/Sydney",
        regular_open=time(10, 0),
        regular_close=time(16, 0),
    ),
    MarketSession(
        key="tokyo",
        label="Tokyo",
        timezone="Asia/Tokyo",
        regular_open=time(9, 0),
        regular_close=time(15, 30),
    ),
    # CME Globex, which is when ES/NQ/YM/GC/CL are actually tradeable. Without
    # this the strip claims everything is shut on a Sunday evening while index
    # futures have been open for hours. Each session opens 18:00 ET and closes
    # 17:00 ET the following day; the daily 17:00-18:00 ET maintenance break
    # falls out naturally as the gap between a close and the next open.
    MarketSession(
        key="cme",
        label="CME futures",
        timezone="America/New_York",
        regular_open=time(18, 0),
        regular_close=time(17, 0),
        # Days the session OPENS: Sunday evening through Thursday evening.
        trading_days=(6, 0, 1, 2, 3),
        overnight=True,
    ),
)

SESSIONS_BY_KEY = {session.key: session for session in SESSIONS}


@dataclass(frozen=True)
class SessionState:
    key: str
    label: str
    timezone: str
    phase: str
    phase_label: str
    local_time: str
    is_open: bool
    next_phase: str
    next_phase_label: str
    next_transition_at: datetime
    seconds_to_next: int

    @property
    def countdown(self) -> str:
        return format_countdown(self.seconds_to_next)


def format_countdown(seconds: int) -> str:
    """Render seconds as the compact `1h 58m` / `12m` / `45s` form."""
    seconds = max(0, seconds)
    days, remainder = divmod(seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, secs = divmod(remainder, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{secs}s"


def _boundaries_for_date(
    session: MarketSession, day: date
) -> list[tuple[datetime, str]]:
    """Phase transitions occurring on ``day``, as aware local datetimes.

    Returns an empty list for non-trading days, which is what makes a Friday
    close roll correctly to the following Monday's pre-market.
    """
    if day.weekday() not in session.trading_days:
        return []

    zone = session.zone

    if session.overnight:
        # Opens on `day`, closes on the following calendar day. Emitting both
        # boundaries here keeps the surrounding search (which sorts across a
        # multi-day window) unchanged.
        return [
            (datetime.combine(day, session.regular_open, tzinfo=zone), OPEN),
            (
                datetime.combine(
                    day + timedelta(days=1), session.regular_close, tzinfo=zone
                ),
                CLOSED,
            ),
        ]

    boundaries: list[tuple[datetime, str]] = []
    if session.pre_market_open is not None:
        boundaries.append(
            (datetime.combine(day, session.pre_market_open, tzinfo=zone), PRE_MARKET)
        )
    boundaries.append((datetime.combine(day, session.regular_open, tzinfo=zone), OPEN))
    boundaries.append(
        (
            datetime.combine(day, session.regular_close, tzinfo=zone),
            AFTER_HOURS if session.after_hours_close is not None else CLOSED,
        )
    )
    if session.after_hours_close is not None:
        boundaries.append(
            (datetime.combine(day, session.after_hours_close, tzinfo=zone), CLOSED)
        )
    return boundaries


def _surrounding_boundaries(
    session: MarketSession, now: datetime
) -> tuple[str, datetime, str]:
    """Return ``(current_phase, next_transition_utc, next_phase)``."""
    local_now = now.astimezone(session.zone)
    today = local_now.date()

    collected: list[tuple[datetime, str]] = []
    for offset in range(-_SEARCH_DAYS, _SEARCH_DAYS + 1):
        collected.extend(_boundaries_for_date(session, today + timedelta(days=offset)))
    collected.sort(key=lambda item: item[0])

    current_phase = CLOSED
    for moment, phase in collected:
        if moment <= local_now:
            current_phase = phase
        else:
            return current_phase, moment.astimezone(now.tzinfo or moment.tzinfo), phase

    # Only reachable if the search window held no future boundary at all.
    fallback = local_now + timedelta(days=1)
    return current_phase, fallback, CLOSED


def session_state(session: MarketSession, now: datetime) -> SessionState:
    phase, next_at, next_phase = _surrounding_boundaries(session, now)
    local_now = now.astimezone(session.zone)
    return SessionState(
        key=session.key,
        label=session.label,
        timezone=session.timezone,
        phase=phase,
        phase_label=PHASE_LABELS[phase],
        local_time=local_now.strftime("%H:%M:%S"),
        is_open=phase == OPEN,
        next_phase=next_phase,
        next_phase_label=PHASE_LABELS[next_phase],
        next_transition_at=next_at,
        seconds_to_next=int((next_at - now).total_seconds()),
    )


def all_session_states(now: datetime) -> list[SessionState]:
    return [session_state(session, now) for session in SESSIONS]
