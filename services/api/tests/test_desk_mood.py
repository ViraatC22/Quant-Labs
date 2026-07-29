"""Risk-mood derivation tests.

The sign conventions are the whole risk here: a rising USDJPY is a weakening
yen and therefore risk-ON, and getting that backwards flips the entire gauge.
"""

from app.services.desk.mood import MIXED, RISK_OFF, RISK_ON, derive_mood


def test_rallying_risk_assets_and_sold_havens_read_risk_on() -> None:
    mood = derive_mood(
        {
            "ES": 0.8,
            "NQ": 1.0,
            "BTC": 1.5,
            "XAUUSD": -0.5,   # gold sold
            "USDJPY": 0.6,    # yen weakening
            "USDCHF": 0.4,    # franc weakening
        }
    )
    assert mood.mood == RISK_ON
    assert mood.spread > 0


def test_haven_bid_with_equities_sold_reads_risk_off() -> None:
    mood = derive_mood(
        {
            "ES": -0.9,
            "NQ": -1.2,
            "BTC": -2.0,
            "XAUUSD": 0.8,
            "USDJPY": -0.7,   # yen strengthening
            "USDCHF": -0.5,
        }
    )
    assert mood.mood == RISK_OFF


def test_usdjpy_sign_convention_is_inverted() -> None:
    # Rising USDJPY = weakening yen: its haven contribution must push the
    # gauge toward risk-ON (positive contribution), not risk-off.
    mood = derive_mood({"ES": 0.0, "USDJPY": 1.0, "XAUUSD": 0.0})
    yen = next(item for item in mood.components if item.symbol == "USDJPY")
    assert yen.contribution > 0


def test_everything_moving_together_reads_mixed() -> None:
    mood = derive_mood(
        {
            "ES": 0.3,
            "NQ": 0.3,
            "BTC": 0.3,
            "XAUUSD": 0.3,
            "USDJPY": -0.3,
            "USDCHF": -0.3,
        }
    )
    assert mood.mood == MIXED
    assert "moving together" in mood.summary


def test_missing_one_side_is_mixed_with_a_stated_reason() -> None:
    # Havens only — no risk assets loaded: refusing to call it is correct.
    mood = derive_mood({"XAUUSD": 1.0, "USDJPY": -1.0}, unavailable=("ES", "NQ", "BTC"))
    assert mood.mood == MIXED
    assert "Not enough" in mood.summary
    assert "ES" in mood.unavailable


def test_the_caveat_always_states_delayed_and_descriptive() -> None:
    mood = derive_mood({"ES": 1.0, "XAUUSD": -1.0})
    assert "delayed" in mood.caveat
    assert "not a regime forecast" in mood.caveat
