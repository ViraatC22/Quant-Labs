"""Cross-asset coverage: indices, commodities, and the CME session.

Two things here are load-bearing. First, index/commodity symbols must resolve
to the *futures* leg where one exists, because Yahoo publishes volume for `=F`
contracts and none for `^` cash indices — no volume means no Flow reading.
Second, the CME session must be open on a Sunday evening, when every
equity/FX venue is shut but ES has been trading for hours.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.desk.sessions import (
    CLOSED,
    OPEN,
    SESSIONS_BY_KEY,
    all_session_states,
    session_state,
)
from app.services.desk.strength import (
    FLOW_BASKET,
    FX_MAJORS,
    capital_flow,
    currency_strength,
)
from app.services.market_data import (
    ASSET_COMMODITY,
    ASSET_CRYPTO,
    ASSET_FX,
    ASSET_INDEX,
    asset_class_for,
    price_basis_for,
    resolve_provider_symbol,
)

CME = SESSIONS_BY_KEY["cme"]


# --- symbol resolution -------------------------------------------------------


@pytest.mark.parametrize(
    ("symbol", "provider_symbol"),
    [
        ("ES", "ES=F"),
        ("US500", "ES=F"),
        ("SPX500", "ES=F"),
        ("NQ", "NQ=F"),
        ("US100", "NQ=F"),
        ("NAS100", "NQ=F"),
        ("NASDAQ", "NQ=F"),
        ("US30", "YM=F"),
        ("DOW", "YM=F"),
        ("GOLD", "GC=F"),
        ("SILVER", "SI=F"),
        ("OIL", "CL=F"),
        ("WTI", "CL=F"),
        ("BRENT", "BZ=F"),
        ("COPPER", "HG=F"),
        ("NATGAS", "NG=F"),
    ],
)
def test_friendly_names_resolve_to_futures(symbol: str, provider_symbol: str) -> None:
    resolved, _ = resolve_provider_symbol(symbol)
    assert resolved == provider_symbol


def test_index_and_commodity_futures_are_last_trade_not_indicative() -> None:
    # Unlike FX (`=X`, an indicative mid), futures print real trades.
    for symbol in ("ES", "NQ", "GC", "CL"):
        provider_symbol, _ = resolve_provider_symbol(symbol)
        assert price_basis_for(provider_symbol) == "last_trade"


def test_asset_classes_are_assigned_correctly() -> None:
    assert asset_class_for("ES") == ASSET_INDEX
    assert asset_class_for("US100") == ASSET_INDEX
    assert asset_class_for("DAX") == ASSET_INDEX  # cash index
    assert asset_class_for("GC") == ASSET_COMMODITY
    assert asset_class_for("OIL") == ASSET_COMMODITY
    assert asset_class_for("XAUUSD") == ASSET_COMMODITY  # futures-proxied spot
    assert asset_class_for("EURUSD") == ASSET_FX
    assert asset_class_for("BTC") == ASSET_CRYPTO


def test_cash_indices_are_available_but_flagged_by_class() -> None:
    # These resolve, but carry no volume upstream — callers should expect Flow
    # to read "unavailable" for them.
    for symbol in ("DAX", "UK100", "JP225", "SPX"):
        provider_symbol, _ = resolve_provider_symbol(symbol)
        assert provider_symbol.startswith("^")
        assert asset_class_for(symbol) == ASSET_INDEX


# --- baskets -----------------------------------------------------------------


def test_flow_basket_is_cross_asset_and_contains_every_fx_major() -> None:
    assert set(FX_MAJORS) <= set(FLOW_BASKET)
    classes = {asset_class_for(symbol) for symbol in FLOW_BASKET}
    assert ASSET_INDEX in classes
    assert ASSET_COMMODITY in classes
    assert ASSET_FX in classes


def test_indices_rank_in_capital_flow() -> None:
    flow = capital_flow({"ES": 1.2, "EURUSD": -0.3, "GC": 0.4})
    assert [item.symbol for item in flow] == ["ES", "GC", "EURUSD"]


def test_indices_never_pollute_currency_strength() -> None:
    # ES has no second currency to decompose into; feeding it to the strength
    # meter would be meaningless, so it must be ignored entirely.
    result = currency_strength({"ES": 5.0, "NQ": 4.0, "GC": 3.0, "EURUSD": 1.0})
    assert {item.currency for item in result} == {"EUR", "USD"}


# --- CME session -------------------------------------------------------------


def test_futures_are_open_on_sunday_evening_when_every_venue_is_shut() -> None:
    # 2026-07-26 is a Sunday; 22:00Z is 18:00 ET, the Globex open.
    sunday_evening = datetime(2026, 7, 26, 22, 30, tzinfo=UTC)
    assert session_state(CME, sunday_evening).phase == OPEN

    others = [
        state
        for state in all_session_states(sunday_evening)
        if state.key != "cme"
    ]
    assert all(state.phase == CLOSED for state in others)


def test_daily_maintenance_break_reads_closed() -> None:
    # Monday 21:30Z is 17:30 ET — inside the 17:00-18:00 ET halt.
    state = session_state(CME, datetime(2026, 7, 27, 21, 30, tzinfo=UTC))
    assert state.phase == CLOSED
    assert state.next_phase == OPEN
    assert state.seconds_to_next == 30 * 60


def test_session_spans_midnight_into_the_next_day() -> None:
    # 02:00Z Tuesday is 22:00 ET Monday — mid-session, opened the prior evening.
    state = session_state(CME, datetime(2026, 7, 28, 2, 0, tzinfo=UTC))
    assert state.phase == OPEN


def test_friday_close_rolls_to_sunday_open() -> None:
    # Friday 21:30Z is 17:30 ET, after the weekly close.
    state = session_state(CME, datetime(2026, 7, 24, 21, 30, tzinfo=UTC))
    assert state.phase == CLOSED
    reopen = state.next_transition_at.astimezone(CME.zone)
    assert reopen.weekday() == 6  # Sunday
    assert reopen.hour == 18


def test_cme_phase_is_continuous_across_a_full_week() -> None:
    start = datetime(2026, 7, 20, 0, 0, tzinfo=UTC)
    for hour in range(24 * 7):
        state = session_state(CME, start + timedelta(hours=hour))
        assert state.seconds_to_next >= 0
        assert state.phase in {OPEN, CLOSED}
