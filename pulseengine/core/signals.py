"""
src/signals.py — Signal scoring, event detection, and news-asset correlation.

Single responsibility: turn price metrics, momentum data, and news articles
into a single composite signal score and enriched article matches.

Pipeline role (steps 4, 5, and 5.5 of the full engine):
  - correlate_news       : match articles to an asset using weighted keywords + recency
  - detect_events        : scan text for known macroeconomic event patterns
  - compute_signal_score : combine price, momentum, sentiment, and context into
                           a -10 to +10 composite bullish/bearish score
"""

from __future__ import annotations

import datetime as dt
import logging
import re

from .config import (
    ASSET_CLASS_WEIGHTS,
    ASSET_KEYWORDS,
    EVENT_TRIGGERS,
    LOW_NEWS_SENTIMENT_WEIGHT_MULTIPLIER,
    MIN_NEWS_ARTICLES_FOR_CONFIDENCE,
    SIGNAL_THRESHOLDS,
    SOURCE_WEIGHTS,
)
from .sentiment import score_sentiment

log = logging.getLogger(__name__)

# Compiled keyword patterns, built once and reused across all correlate_news calls.
# Word boundaries (\b) on each alphanumeric end prevent substring false-positives
# (e.g. "gold" matching "goldman", "oil" matching "broil").
_KW_PATTERN_CACHE: dict[str, re.Pattern] = {}


def _kw_re(kw: str) -> re.Pattern:
    """Return a compiled regex that matches *kw* as a whole token in lowercase text."""
    if kw not in _KW_PATTERN_CACHE:
        escaped = re.escape(kw)
        prefix  = r'\b'
        suffix  = r'\b' if kw[-1].isalnum() else ''
        _KW_PATTERN_CACHE[kw] = re.compile(prefix + escaped + suffix)
    return _KW_PATTERN_CACHE[kw]



# ── News-asset correlation ────────────────────────────────────────────────────

def correlate_news(
    asset_name: str,
    articles: list[dict],
    keywords: list[str] | None = None,
) -> list[dict]:
    """
    Match articles to *asset_name* using weighted keywords, a recency bonus,
    and a source-credibility multiplier.

    When *keywords* is provided, those terms are added as medium-weight
    relevance terms. This enables arbitrary ticker support without modifying
    ASSET_KEYWORDS.

    Returns a list of enriched article dicts (with relevance_score, sentiment,
    and events_detected fields) sorted by descending relevance.
    """
    kw_pairs = list(
        ASSET_KEYWORDS.get(asset_name)
        or ASSET_KEYWORDS.get(asset_name.title(), [])
    )
    kw_pairs.append((asset_name.lower(), 2))

    if keywords:
        for kw in keywords:
            clean = (kw or "").strip().lower()
            if len(clean) >= 3:
                kw_pairs.append((clean, 2))

    now = dt.datetime.now(dt.timezone.utc)
    matched: list[dict] = []
    for article in articles:
        text  = article["title"] + " " + article["summary"]
        blob  = text.lower()
        score = sum(w for kw, w in kw_pairs if _kw_re(kw).search(blob))

        if score <= 0:
            continue

        # Recency bonus: articles < 24 h old get +2; < 48 h get +1
        recency_bonus = 0
        if article.get("published"):
            age_h = (
                now - article["published"]
            ).total_seconds() / 3600
            if age_h < 24:
                recency_bonus = 2
            elif age_h < 48:
                recency_bonus = 1

        src_weight  = SOURCE_WEIGHTS.get(article.get("source", ""), 1.0)
        final_score = round((score + recency_bonus) * src_weight, 2)

        sentiment = score_sentiment(text)
        events    = detect_events(text)

        matched.append({
            **article,
            "relevance_score": final_score,
            "base_score":      score,
            "source_weight":   src_weight,
            "sentiment":       sentiment,
            "events_detected": events,
        })

    matched.sort(key=lambda a: a["relevance_score"], reverse=True)
    return matched


# ── Event detection ───────────────────────────────────────────────────────────

def detect_events(text: str) -> list[dict]:
    """Scan *text* for known event patterns from config.EVENT_TRIGGERS."""
    text_lower = text.lower()
    found: list[dict] = []
    for key, info in EVENT_TRIGGERS.items():
        hits = [kw for kw in info["keywords"] if kw in text_lower]
        if hits:
            found.append({
                "event_key":  key,
                "label":      info["label"],
                "icon":       info["icon"],
                "matched_kw": hits,
            })
    return found


# ── Composite signal scoring ──────────────────────────────────────────────────

def compute_signal_score(
    metrics: dict,
    momentum: dict,
    news: list[dict],
    market_ctx: dict | None = None,
    category: str | None = None,
) -> dict:
    """
    Compute a composite bullish/bearish signal for an asset.

    Raw component max contributions (before per-class weighting):
      trend          +/- 2.0   (7d vs 30d MA direction)
      momentum       +/- 2.0   (10-day rate of change, normalised)
      rsi            +/- 1.0   (overbought / oversold positioning)
      sentiment      +/- 2.0   (news sentiment average)
      trend_strength +/- 1.0   (magnitude of MA divergence)
      context        +/- 1.0   (sector / market alignment)

    Per-class weights from ASSET_CLASS_WEIGHTS scale each component.
    Weak signals between -1.0 and +1.0 are labelled "Neutral".
    Total is clamped to [-10, +10].
    """
    news_article_count = len(news)
    low_news_confidence = news_article_count < MIN_NEWS_ARTICLES_FOR_CONFIDENCE

    if not metrics:
        return {
            "score": 0.0,
            "label": "No Data",
            "low_news_confidence": low_news_confidence,
            "news_article_count": news_article_count,
            "components": {},
            "raw_components": {},
        }

    raw: dict[str, float] = {}

    # 1. Price trend
    trend = metrics.get("trend", "sideways")
    raw["trend"] = {"uptrend": 2.0, "downtrend": -2.0, "sideways": 0.0}.get(trend, 0.0)

    # 2. ROC momentum
    roc = momentum.get("roc_10d", 0.0)
    raw["momentum"] = round(max(-2.0, min(2.0, roc / 5.0)), 2)

    # 3. RSI positioning
    rsi = momentum.get("rsi", 50.0)
    if rsi > 70:
        raw["rsi"] = -1.0       # overbought
    elif rsi < 30:
        raw["rsi"] = 1.0        # oversold (mean-reversion bullish)
    elif rsi > 55:
        raw["rsi"] = 0.5
    elif rsi < 45:
        raw["rsi"] = -0.5
    else:
        raw["rsi"] = 0.0

    # 4. News sentiment
    if news:
        avg_sent = sum(a.get("sentiment", {}).get("compound", 0.0) for a in news) / len(news)
        sentiment_raw = max(-2.0, min(2.0, avg_sent * 4.0))
        if low_news_confidence:
            sentiment_raw *= LOW_NEWS_SENTIMENT_WEIGHT_MULTIPLIER
        raw["sentiment"] = round(sentiment_raw, 2)
    else:
        raw["sentiment"] = 0.0

    # 5. Trend strength (3 % MA divergence = full 1.0 score)
    ts = momentum.get("trend_strength", 0.0)
    raw["trend_strength"] = round(max(-1.0, min(1.0, ts / 3.0)), 2)

    # 6. Market context alignment
    ctx_score = 0.0
    if market_ctx:
        chg_1d = metrics.get("change_1d")
        if chg_1d is not None:
            direction = 1.0 if chg_1d > 0 else -1.0
            if market_ctx.get("is_market_wide"):
                ctx_score += direction * 0.5
            if market_ctx.get("is_sector_wide"):
                ctx_score += direction * 0.5
    raw["context"] = round(ctx_score, 2)

    # Apply per-class multipliers
    class_weights = ASSET_CLASS_WEIGHTS.get(category, {}) if category else {}
    components: dict[str, float] = {
        k: round(v * class_weights.get(k, 1.0), 2)
        for k, v in raw.items()
    }

    total = round(max(-10.0, min(10.0, sum(components.values()))), 2)

    if total >= SIGNAL_THRESHOLDS["strong_bullish"]:
        label = "Strong Bullish"
    elif total >= SIGNAL_THRESHOLDS["bullish"]:
        label = "Bullish"
    elif total >= SIGNAL_THRESHOLDS["slightly_bullish"]:
        label = "Slightly Bullish"
    elif total > SIGNAL_THRESHOLDS["neutral"]:
        label = "Neutral"
    elif total >= SIGNAL_THRESHOLDS["slightly_bearish"]:
        label = "Slightly Bearish"
    elif total >= SIGNAL_THRESHOLDS["bearish"]:
        label = "Bearish"
    else:
        label = "Strong Bearish"

    return {
        "score":          total,
        "label":          label,
        "low_news_confidence": low_news_confidence,
        "news_article_count":  news_article_count,
        "components":     components,
        "raw_components": raw,
        "category":       category,
    }
