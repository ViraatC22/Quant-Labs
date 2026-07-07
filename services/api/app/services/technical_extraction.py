from __future__ import annotations

import re

TECHNICAL_PATTERNS: dict[str, list[tuple[str, str, str]]] = {
    "indicators": [
        (r"\bvwap\b", "VWAP", "vwap"),
        (r"\banchored\s+vwap\b|\bavwap\b", "Anchored VWAP", "anchored-vwap"),
        (r"\bema\b|\bexponential moving average\b", "EMA", "ema"),
        (r"\bsma\b|\bsimple moving average\b", "SMA", "sma"),
        (r"\bma\b|\bmoving average\b", "Moving average", "moving-average"),
        (r"\brsi\b|\brelative strength index\b", "RSI", "rsi"),
        (r"\bmacd\b", "MACD", "macd"),
        (r"\batr\b|\baverage true range\b", "ATR", "atr"),
        (r"\badx\b", "ADX", "adx"),
        (
            r"\bstochastic oscillator\b|\bstochastic indicator\b|\bstoch\b",
            "Stochastic",
            "stochastic",
        ),
        (r"\bbollinger\b|\bbb\b", "Bollinger Bands", "bollinger-bands"),
        (r"\bichimoku\b", "Ichimoku", "ichimoku"),
        (r"\bsupertrend\b", "Supertrend", "supertrend"),
        (r"\bvolume profile\b|\bvwap profile\b", "Volume profile", "volume-profile"),
        (r"\brelative volume\b|\brvol\b", "Relative volume", "relative-volume"),
    ],
    "price_action": [
        (r"\bsupport\b", "Support", "support"),
        (r"\bresistance\b", "Resistance", "resistance"),
        (r"\btrendline\b|\btrend line\b", "Trendline", "trendline"),
        (r"\bchannel\b", "Channel", "channel"),
        (r"\bbreakout\b", "Breakout", "breakout"),
        (r"\bbreakdown\b", "Breakdown", "breakdown"),
        (r"\bpullback\b", "Pullback", "pullback"),
        (r"\breversal\b", "Reversal", "reversal"),
        (r"\bcontinuation\b", "Continuation", "continuation"),
        (r"\bconsolidation\b|\brange\b", "Range", "range"),
        (r"\bgap fill\b", "Gap fill", "gap-fill"),
        (r"\bgap up\b|\bgap down\b", "Gap", "gap"),
    ],
    "market_structure": [
        (r"\bmarket structure\b", "Market structure", "market-structure"),
        (r"\bbreak of structure\b|\bbos\b", "Break of structure", "break-of-structure"),
        (r"\bchange of character\b|\bchoch\b", "Change of character", "change-of-character"),
        (r"\bliquidity sweep\b|\bsweep\b", "Liquidity sweep", "liquidity-sweep"),
        (r"\bliquidity grab\b", "Liquidity grab", "liquidity-grab"),
        (r"\bstop hunt\b", "Stop hunt", "stop-hunt"),
        (r"\border block\b|\bob\b", "Order block", "order-block"),
        (r"\bfair value gap\b|\bfvg\b", "Fair value gap", "fair-value-gap"),
        (r"\bimbalance\b", "Imbalance", "imbalance"),
        (r"\bsupply\b|\bdemand\b", "Supply demand", "supply-demand"),
        (
            r"\bhigher high\b|\blower high\b|\bhigher low\b|\blower low\b",
            "Swing structure",
            "swing-structure",
        ),
    ],
    "setups": [
        (r"\bopening range breakout\b|\borb\b", "Opening range breakout", "opening-range-breakout"),
        (r"\bopening range\b", "Opening range", "opening-range"),
        (r"\bvwap pullback\b", "VWAP pullback", "vwap-pullback"),
        (r"\bmean reversion\b", "Mean reversion", "mean-reversion"),
        (r"\btrend following\b", "Trend following", "trend-following"),
        (r"\bscalp\b|\bscalping\b", "Scalp", "scalp"),
        (r"\bswing\b", "Swing", "swing"),
        (r"\bmomentum\b", "Momentum", "momentum"),
        (r"\bfade\b", "Fade", "fade"),
        (r"\breclaim\b", "Reclaim", "reclaim"),
        (r"\bretest\b", "Retest", "retest"),
    ],
    "risk": [
        (r"\bstop loss\b|\bstop\b", "Stop loss", "stop-loss"),
        (r"\binvalidation\b", "Invalidation", "invalidation"),
        (r"\btake profit\b|\bprofit target\b|\btarget\b", "Profit target", "profit-target"),
        (r"\brisk reward\b|\br:r\b|\brr\b", "Risk reward", "risk-reward"),
        (r"\bposition siz(e|ing)\b|\bsize\b", "Position sizing", "position-sizing"),
        (r"\btrailing stop\b|\btrail\b", "Trailing stop", "trailing-stop"),
    ],
    "sessions": [
        (r"\bpremarket\b|\bpre-market\b", "Premarket", "premarket"),
        (r"\bopen\b|\bopening bell\b", "Open", "open"),
        (r"\blondon\b", "London", "london-session"),
        (r"\bnew york\b|\bny session\b", "New York", "new-york-session"),
        (r"\bpower hour\b", "Power hour", "power-hour"),
    ],
    "markets": [
        (r"\bfutures\b|\bes\b|\bnq\b", "Futures", "futures"),
        (r"\boptions\b", "Options", "options"),
        (r"\bcrypto\b|\bbtc\b|\beth\b", "Crypto", "crypto"),
        (r"\bforex\b|\bfx\b", "Forex", "forex"),
        (r"\bequity\b|\bstock\b|\bspy\b|\bqqq\b", "Equities", "equities"),
    ],
}

TECHNICAL_ALIASES = {
    "avwap",
    "bos",
    "choch",
    "fvg",
    "orb",
    "rr",
    "rvol",
}

TIMEFRAME_REGEX = (
    r"\b(?:1|2|3|5|10|15|30|45|60)[ -]?"
    r"(?:s|sec|m|min|minute|h|hr|hour)s?\b"
    r"|\b(?:daily|weekly|monthly|intraday)\b"
)


def extract_technical_profile(text: str) -> dict[str, list[str]]:
    profile: dict[str, list[str]] = {}
    for category, patterns in TECHNICAL_PATTERNS.items():
        labels = {
            label
            for pattern, label, _tag in patterns
            if re.search(pattern, text, re.IGNORECASE)
        }
        if labels:
            profile[category] = sorted(labels)

    timeframes = {
        match.group(0).upper().replace("MINUTE", "min").replace("MINUTES", "min")
        for match in re.finditer(TIMEFRAME_REGEX, text, re.IGNORECASE)
    }
    if timeframes:
        profile["timeframes"] = sorted(timeframes)
    return profile


def technical_tags_from_profile(profile: dict[str, list[str]]) -> list[str]:
    tags: set[str] = set()
    for category, labels in profile.items():
        for label in labels:
            tags.add(_slug(label))
            tags.add(f"{category.rstrip('s')}:{_slug(label)}")
    return sorted(tags)


def extract_technical_tags(text: str) -> list[str]:
    profile = extract_technical_profile(text)
    tags = set(technical_tags_from_profile(profile))
    for patterns in TECHNICAL_PATTERNS.values():
        for pattern, _label, tag in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                tags.add(tag)
    return sorted(tags)


def is_technical_tag(value: str) -> bool:
    return _slug(value) in known_technical_tags()


def known_technical_tags() -> set[str]:
    tags = set(TECHNICAL_ALIASES)
    for category, patterns in TECHNICAL_PATTERNS.items():
        for _pattern, label, tag in patterns:
            slug = _slug(label)
            tags.update({tag, slug, f"{category.rstrip('s')}:{slug}"})
    return tags


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
