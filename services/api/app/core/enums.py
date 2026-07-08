"""Canonical domain enums shared across schemas and services.

These are the validated vocabularies for inputs. Read schemas keep plain ``str``
so legacy rows with out-of-vocabulary values never break a list response, but
every write is validated against these.
"""

from __future__ import annotations

from enum import StrEnum


class TradeSide(StrEnum):
    long = "long"
    short = "short"


class AssetClass(StrEnum):
    equity = "equity"
    option = "option"
    future = "future"
    crypto = "crypto"
    forex = "forex"


class TradeStatus(StrEnum):
    open = "open"
    closed = "closed"


# Contract multipliers per asset class when the client does not supply one.
# Options control 100 shares; futures multipliers are symbol-specific and are
# resolved on the client, so the server default is 1 unless told otherwise.
DEFAULT_CONTRACT_MULTIPLIER: dict[str, int] = {
    AssetClass.equity: 1,
    AssetClass.option: 100,
    AssetClass.future: 1,
    AssetClass.crypto: 1,
    AssetClass.forex: 1,
}
