"""
src/sentiment.py — Sentiment analysis for financial text.

Single responsibility: score the emotional polarity of a text string.

Uses VADER with a custom financial lexicon injected at import time.
Falls back to a simple positive/negative keyword counter when VADER is
not installed.

Public API:
  score_sentiment(text) → {"compound", "pos", "neg", "neu"}
  VADER_AVAILABLE        → bool (advertised to callers that care)
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

# ── VADER setup ──────────────────────────────────────────────────────────────

try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    _vader = SentimentIntensityAnalyzer()
    VADER_AVAILABLE = True
except ImportError:
    SentimentIntensityAnalyzer = None  # type: ignore[assignment,misc]
    _vader = None
    VADER_AVAILABLE = False

# ── Financial lexicon ────────────────────────────────────────────────────────

FINANCE_LEXICON: dict[str, float] = {
    "surge": 2.5, "surges": 2.5, "surging": 2.5, "rally": 2.2,
    "rallies": 2.2, "rallying": 2.2, "bullish": 2.5, "soar": 2.8,
    "soars": 2.8, "soaring": 2.8, "breakout": 2.0, "upbeat": 1.8,
    "outperform": 2.0, "outperforms": 2.0, "beat": 1.5, "beats": 1.5,
    "upgrade": 2.0, "upgraded": 2.0, "boom": 2.5, "booming": 2.5,
    "recovery": 1.8, "rebound": 2.0, "rebounds": 2.0, "uptick": 1.5,
    "momentum": 1.3, "expansion": 1.5,
    "crash": -3.0, "crashes": -3.0, "crashing": -3.0, "plunge": -2.8,
    "plunges": -2.8, "plunging": -2.8, "bearish": -2.5, "slump": -2.2,
    "slumps": -2.2, "selloff": -2.5, "sell-off": -2.5, "tumble": -2.5,
    "tumbles": -2.5, "downturn": -2.2, "recession": -2.5,
    "downgrade": -2.0, "downgraded": -2.0, "contraction": -2.0,
    "misses": -1.8, "underperform": -2.0, "underperforms": -2.0,
}

if VADER_AVAILABLE and _vader is not None:
    _vader.lexicon.update(FINANCE_LEXICON)

# ── Fallback keyword sets ─────────────────────────────────────────────────────

_POS_WORDS = frozenset([
    "surge", "rally", "gain", "rise", "jump", "climb", "boom", "bullish",
    "record", "high", "profit", "growth", "recovery", "optimism", "strong",
    "upgrade", "beat", "exceed", "soar", "breakout", "expansion", "upbeat",
])
_NEG_WORDS = frozenset([
    "crash", "drop", "fall", "plunge", "sink", "decline", "slump", "bearish",
    "low", "loss", "recession", "fear", "crisis", "panic", "weak", "downgrade",
    "miss", "risk", "sell-off", "tumble", "contraction", "downturn", "collapse",
])


# ── Public API ────────────────────────────────────────────────────────────────

def score_sentiment(text: str) -> dict:
    """
    Return {"compound": float, "pos": float, "neg": float, "neu": float}.

    Uses VADER with the injected financial lexicon; falls back to keyword
    counting if VADER is unavailable.
    """
    if VADER_AVAILABLE and _vader is not None:
        try:
            s = _vader.polarity_scores(text)
            return {"compound": s["compound"], "pos": s["pos"], "neg": s["neg"], "neu": s["neu"]}
        except (TypeError, UnicodeDecodeError, KeyError):
            log.debug("VADER failed on text (len=%d), using fallback", len(text))
    return _fallback_sentiment(text)


def _fallback_sentiment(text: str) -> dict:
    """Simple keyword-count fallback used when VADER is not installed."""
    words = set(text.lower().split())
    p     = len(words & _POS_WORDS)
    n     = len(words & _NEG_WORDS)
    total = p + n or 1
    return {
        "compound": round((p - n) / total, 4),
        "pos":      round(p / total, 4),
        "neg":      round(n / total, 4),
        "neu":      round(1.0 - (p / total) - (n / total), 4),
    }
