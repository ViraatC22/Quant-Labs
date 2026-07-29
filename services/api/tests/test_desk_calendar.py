"""Economic calendar tests.

The two failure modes that actually matter here are timezone handling (a wrong
hour puts every event in the wrong session) and encoding (windows-1252 payload
decoded as UTF-8 mangles European names). Both are pinned below.
"""

from datetime import UTC, datetime

import pytest

from app.services.desk import calendar as calendar_service
from app.services.desk.calendar import (
    IMPACT_HIGH,
    IMPACT_HOLIDAY,
    IMPACT_LOW,
    IMPACT_MEDIUM,
    fetch_calendar,
)

SAMPLE = """<?xml version="1.0" encoding="windows-1252"?>
<weeklyevents>
  <event>
    <title>ECB Main Refinancing Rate</title>
    <country>EUR</country>
    <date><![CDATA[07-23-2026]]></date>
    <time><![CDATA[12:15pm]]></time>
    <impact><![CDATA[High]]></impact>
    <forecast><![CDATA[2.40%]]></forecast>
    <previous><![CDATA[2.40%]]></previous>
    <url><![CDATA[https://example.com/ecb]]></url>
  </event>
  <event>
    <title>ECB's Vujcic speech</title>
    <country>EUR</country>
    <date><![CDATA[07-23-2026]]></date>
    <time><![CDATA[7:45am]]></time>
    <impact><![CDATA[Medium]]></impact>
  </event>
  <event>
    <title>Bank Holiday</title>
    <country>JPY</country>
    <date><![CDATA[07-20-2026]]></date>
    <time><![CDATA[All Day]]></time>
    <impact><![CDATA[Holiday]]></impact>
  </event>
  <event>
    <title>Tentative Budget Release</title>
    <country>GBP</country>
    <date><![CDATA[07-22-2026]]></date>
    <time><![CDATA[Tentative]]></time>
    <impact><![CDATA[Low]]></impact>
  </event>
  <event>
    <title>Midnight Print</title>
    <country>USD</country>
    <date><![CDATA[07-21-2026]]></date>
    <time><![CDATA[12:00am]]></time>
    <impact><![CDATA[Low]]></impact>
  </event>
  <event>
    <title>No Date Event</title>
    <country>USD</country>
    <time><![CDATA[9:00am]]></time>
    <impact><![CDATA[Low]]></impact>
  </event>
</weeklyevents>
"""


@pytest.fixture(autouse=True)
def clear_calendar_cache():
    calendar_service._cache = None
    yield
    calendar_service._cache = None


def _install(monkeypatch, payload: str | bytes, *, fail: bool = False):
    calls = {"n": 0}
    raw = payload.encode("windows-1252") if isinstance(payload, str) else payload

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, _limit=None):
            return raw

    def fake_open(url, timeout, headers=None):
        calls["n"] += 1
        if fail:
            raise TimeoutError("provider down")
        return _FakeResponse()

    monkeypatch.setattr(calendar_service, "safe_urlopen", fake_open)
    return calls


def test_events_parse_with_utc_timestamps(monkeypatch) -> None:
    # The feed publishes UTC. ECB's 14:15 CEST announcement arrives as 12:15pm,
    # and must land on 12:15Z — not 14:15, and not shifted by a local offset.
    _install(monkeypatch, SAMPLE)
    feed = fetch_calendar()
    assert feed.available is True

    ecb = next(e for e in feed.events if e.title.startswith("ECB Main"))
    assert ecb.scheduled_at == datetime(2026, 7, 23, 12, 15, tzinfo=UTC)
    assert ecb.currency == "EUR"
    assert ecb.impact == IMPACT_HIGH
    assert ecb.forecast == "2.40%"
    assert ecb.is_high_impact is True


def test_midnight_is_parsed_as_zero_hundred(monkeypatch) -> None:
    # 12:00am is 00:00, not 12:00 — a classic 12-hour clock off-by-twelve.
    _install(monkeypatch, SAMPLE)
    event = next(e for e in fetch_calendar().events if e.title == "Midnight Print")
    assert event.scheduled_at == datetime(2026, 7, 21, 0, 0, tzinfo=UTC)


def test_windows_1252_payload_is_decoded_correctly(monkeypatch) -> None:
    # Decoding this as UTF-8 raises or mangles the c-with-caron.
    payload = SAMPLE.replace("Vujcic", "Vujčić").encode("windows-1252", errors="replace")
    _install(monkeypatch, payload)
    titles = [e.title for e in fetch_calendar().events]
    assert any("Vuj" in title for title in titles)
    # The mojibake signature of a UTF-8 misread must not appear.
    assert not any("Ä" in title or "Ã" in title for title in titles)


def test_all_day_and_tentative_events_have_no_time(monkeypatch) -> None:
    _install(monkeypatch, SAMPLE)
    events = {e.title: e for e in fetch_calendar().events}

    holiday = events["Bank Holiday"]
    assert holiday.all_day is True
    assert holiday.scheduled_at is None
    assert holiday.impact == IMPACT_HOLIDAY

    tentative = events["Tentative Budget Release"]
    assert tentative.tentative is True
    assert tentative.scheduled_at is None
    assert tentative.impact == IMPACT_LOW


def test_events_without_a_date_are_dropped(monkeypatch) -> None:
    _install(monkeypatch, SAMPLE)
    assert not any(e.title == "No Date Event" for e in fetch_calendar().events)


def test_timed_events_sort_before_undated_ones(monkeypatch) -> None:
    _install(monkeypatch, SAMPLE)
    events = fetch_calendar().events
    first_undated = next(
        (i for i, e in enumerate(events) if e.scheduled_at is None), len(events)
    )
    # Nothing with a timestamp may appear after the first undated entry.
    assert all(e.scheduled_at is None for e in events[first_undated:])


def test_impact_tiers_are_normalized(monkeypatch) -> None:
    _install(monkeypatch, SAMPLE)
    tiers = {e.impact for e in fetch_calendar().events}
    assert tiers <= {IMPACT_HIGH, IMPACT_MEDIUM, IMPACT_LOW, IMPACT_HOLIDAY}


def test_second_call_is_served_from_cache(monkeypatch) -> None:
    calls = _install(monkeypatch, SAMPLE)
    fetch_calendar()
    fetch_calendar()
    assert calls["n"] == 1


def test_outage_serves_stale_cache_flagged_as_stale(monkeypatch) -> None:
    _install(monkeypatch, SAMPLE)
    fetch_calendar()

    monkeypatch.setattr(calendar_service, "CALENDAR_CACHE_TTL_SECONDS", 0.0)
    _install(monkeypatch, SAMPLE, fail=True)
    feed = fetch_calendar()

    assert feed.available is True
    assert feed.stale is True
    assert feed.reason is not None
    assert len(feed.events) > 0


def test_outage_without_cache_is_unavailable_not_fabricated(monkeypatch) -> None:
    _install(monkeypatch, SAMPLE, fail=True)
    feed = fetch_calendar()
    assert feed.available is False
    assert feed.events == ()
    assert feed.reason is not None


def test_malformed_xml_degrades_rather_than_raising(monkeypatch) -> None:
    _install(monkeypatch, "<weeklyevents><event><title>broken")
    feed = fetch_calendar()
    assert feed.available is False
    assert feed.events == ()
