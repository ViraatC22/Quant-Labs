"""Currency strength decomposition tests.

The property that matters: a pair move must contribute equally and oppositely
to its two currencies. Get the sign wrong on the quote side and the meter says
the dollar is strengthening when it is selling off.
"""

import pytest

from app.services.desk.strength import (
    FX_MAJORS,
    capital_flow,
    currency_strength,
    split_pair,
)


def test_split_pair_handles_normal_and_slashed_forms() -> None:
    assert split_pair("EURUSD") == ("EUR", "USD")
    assert split_pair("eur/usd") == ("EUR", "USD")
    assert split_pair(" GBPJPY ") == ("GBP", "JPY")


def test_split_pair_rejects_non_pairs() -> None:
    assert split_pair("AAPL") is None
    assert split_pair("BTC-USD") is None
    assert split_pair("ES") is None
    assert split_pair("") is None


def test_a_pair_move_is_equal_and_opposite_for_its_two_currencies() -> None:
    result = {item.currency: item for item in currency_strength({"EURUSD": 1.0})}
    assert result["EUR"].score == 1.0
    assert result["USD"].score == -1.0


def test_quote_currency_sign_flips_for_usd_base_pairs() -> None:
    # USDJPY rising is dollar strength, not yen strength.
    result = {item.currency: item for item in currency_strength({"USDJPY": 0.6})}
    assert result["USD"].score == 0.6
    assert result["JPY"].score == -0.6


def test_dollar_strength_averages_across_every_pair_it_appears_in() -> None:
    changes = {
        "EURUSD": -1.0,  # USD +1.0
        "GBPUSD": -0.5,  # USD +0.5
        "USDJPY": 0.3,  # USD +0.3
    }
    result = {item.currency: item for item in currency_strength(changes)}
    usd = result["USD"]
    assert usd.pairs == 3
    assert usd.score == pytest.approx(round((1.0 + 0.5 + 0.3) / 3, 3))
    # And the counter-currencies each rest on a single pair.
    assert result["EUR"].pairs == 1
    assert result["JPY"].pairs == 1


def test_results_are_ranked_strongest_first() -> None:
    changes = {"EURUSD": 1.0, "GBPUSD": 0.2, "USDJPY": 0.5}
    scores = [item.score for item in currency_strength(changes)]
    assert scores == sorted(scores, reverse=True)


def test_non_fx_symbols_are_ignored_by_the_strength_meter() -> None:
    result = currency_strength({"AAPL": 3.0, "BTC": 5.0, "EURUSD": 1.0})
    currencies = {item.currency for item in result}
    assert currencies == {"EUR", "USD"}


def test_flat_market_produces_zero_strength() -> None:
    result = currency_strength({pair: 0.0 for pair in FX_MAJORS})
    assert all(item.score == 0.0 for item in result)


def test_contributions_are_recorded_for_auditing() -> None:
    result = {item.currency: item for item in currency_strength({"EURUSD": 1.0})}
    assert result["USD"].contributions == (("EURUSD", -1.0),)
    assert result["EUR"].contributions == (("EURUSD", 1.0),)


def test_capital_flow_ranks_by_change_descending() -> None:
    flow = capital_flow({"A": -1.0, "B": 2.0, "C": 0.5})
    assert [item.symbol for item in flow] == ["B", "C", "A"]
    assert flow[0].change_percent == 2.0


def test_empty_input_produces_empty_output() -> None:
    assert currency_strength({}) == []
    assert capital_flow({}) == []


def test_every_major_currency_is_covered_by_at_least_two_pairs() -> None:
    # A currency appearing in only one pair produces a "strength" that is just
    # that pair restated, so the default basket must not contain one.
    result = currency_strength({pair: 0.1 for pair in FX_MAJORS})
    singles = [item.currency for item in result if item.pairs < 2]
    assert singles == [], f"currencies backed by one pair: {singles}"
