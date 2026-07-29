"""Session phase and countdown tests, with the weekend and DST edges pinned.

`now` is injected everywhere, so these assert real calendar behaviour rather
than whatever the CI clock happens to say.
"""

from datetime import UTC, datetime, timedelta

from app.services.desk.sessions import (
    AFTER_HOURS,
    CLOSED,
    OPEN,
    PRE_MARKET,
    SESSIONS_BY_KEY,
    all_session_states,
    format_countdown,
    session_state,
)

LONDON = SESSIONS_BY_KEY["london"]
NEW_YORK = SESSIONS_BY_KEY["new_york"]
TOKYO = SESSIONS_BY_KEY["tokyo"]


def test_countdown_formatting_steps_down_by_magnitude() -> None:
    assert format_countdown(2 * 86_400 + 3 * 3_600) == "2d 3h"
    assert format_countdown(3_600 + 58 * 60) == "1h 58m"
    assert format_countdown(12 * 60) == "12m"
    assert format_countdown(45) == "45s"
    assert format_countdown(-10) == "0s"


def test_london_open_during_british_summer_time() -> None:
    # 2026-07-24 13:00Z is 14:00 in London (BST, UTC+1) — inside 08:00-16:30.
    state = session_state(LONDON, datetime(2026, 7, 24, 13, 0, tzinfo=UTC))
    assert state.phase == OPEN
    assert state.local_time == "14:00:00"
    assert state.next_phase == CLOSED


def test_london_open_during_winter_is_utc() -> None:
    # 2026-01-15 13:00Z is 13:00 in London (GMT). A fixed +1 offset would be
    # wrong here, which is the whole reason zoneinfo is used.
    state = session_state(LONDON, datetime(2026, 1, 15, 13, 0, tzinfo=UTC))
    assert state.phase == OPEN
    assert state.local_time == "13:00:00"


def test_new_york_pre_market_before_the_bell() -> None:
    # 09:00 EDT — after the 04:00 pre-market start, before the 09:30 open.
    state = session_state(NEW_YORK, datetime(2026, 7, 24, 13, 0, tzinfo=UTC))
    assert state.phase == PRE_MARKET
    assert state.next_phase == OPEN
    assert state.seconds_to_next == 30 * 60
    assert state.countdown == "30m"
    assert state.is_open is False


def test_new_york_after_hours_follows_the_close() -> None:
    # 16:30 EDT — past the 16:00 close, inside the 20:00 after-hours window.
    state = session_state(NEW_YORK, datetime(2026, 7, 24, 20, 30, tzinfo=UTC))
    assert state.phase == AFTER_HOURS
    assert state.next_phase == CLOSED


def test_weekend_is_closed_and_rolls_to_monday() -> None:
    saturday = datetime(2026, 7, 25, 13, 0, tzinfo=UTC)
    state = session_state(LONDON, saturday)
    assert state.phase == CLOSED
    assert state.is_open is False
    # Next transition must land on the following Monday, not Sunday.
    assert state.next_transition_at.astimezone(LONDON.zone).weekday() == 0


def test_friday_evening_rolls_across_the_weekend() -> None:
    # Tokyo is already shut on Friday night; the next open is Monday.
    friday_night = datetime(2026, 7, 24, 13, 0, tzinfo=UTC)
    state = session_state(TOKYO, friday_night)
    assert state.phase == CLOSED
    assert state.next_phase == OPEN
    assert state.next_transition_at.astimezone(TOKYO.zone).weekday() == 0


def test_every_session_reports_a_future_transition() -> None:
    now = datetime(2026, 7, 24, 13, 0, tzinfo=UTC)
    states = all_session_states(now)
    # London, New York, Sydney, Tokyo, plus the CME futures session.
    assert len(states) == 5
    for state in states:
        assert state.seconds_to_next > 0
        assert state.next_transition_at > now
        assert state.phase in {PRE_MARKET, OPEN, AFTER_HOURS, CLOSED}


def test_phase_is_continuous_across_a_full_week() -> None:
    # Step hourly through a week; the phase must never be undefined and the
    # countdown must never go negative.
    start = datetime(2026, 3, 23, 0, 0, tzinfo=UTC)  # includes the US/EU DST gap
    for hour in range(24 * 7):
        now = start + timedelta(hours=hour)
        for state in all_session_states(now):
            assert state.seconds_to_next >= 0
            assert state.phase in {PRE_MARKET, OPEN, AFTER_HOURS, CLOSED}
