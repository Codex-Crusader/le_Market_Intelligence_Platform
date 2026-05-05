"""Additional logic-focused tests for Issue #2 coverage goals."""

from __future__ import annotations

import datetime as dt

import pandas as pd

from pulseengine.core.config import DEDUP_SIMILARITY_THRESHOLD
from pulseengine.core.explanation import _detect_contradictions
from pulseengine.core.news import _jaccard, deduplicate_articles
from pulseengine.core.price import compute_price_metrics, compute_roc
from pulseengine.core.sentiment import score_sentiment
from pulseengine.core.signals import compute_signal_score, correlate_news


def test_compute_price_metrics_known_values(ohlcv_df):
    """Known OHLCV input should produce sane deterministic metric values."""
    prices = pd.Series([100.0, 102.0, 104.0, 106.0, 108.0, 110.0, 112.0, 114.0, 116.0])
    metrics = compute_price_metrics(ohlcv_df(prices))

    assert metrics["latest_price"] == 116.0
    assert metrics["change_1d"] == round(((116.0 - 114.0) / 114.0) * 100, 2)
    assert metrics["change_7d"] == round(((116.0 - 102.0) / 102.0) * 100, 2)
    assert metrics["trend"] == "uptrend"
    assert metrics["volatility"] is not None
    assert metrics["volatility"] >= 0.0


def test_compute_roc_edge_cases():
    """ROC edge behavior should remain safe and non-crashing."""
    assert compute_roc(pd.Series([100.0] * 20), period=10) == 0.0
    assert compute_roc(pd.Series([100.0]), period=10) == 0.0
    assert compute_roc(pd.Series([0.0] + [10.0] * 10), period=10) == 0.0


def test_jaccard_threshold_boundary_behavior():
    """Jaccard scores above/below threshold should be distinguishable."""
    above = _jaccard({"a", "b", "c"}, {"a", "b", "d"})  # 2/4 = 0.5
    below = _jaccard({"a", "b", "c"}, {"a", "b", "c", "d", "e"})  # 3/5 = 0.6

    # Construct one definitely above threshold and one below threshold.
    definitely_above = _jaccard({"a", "b", "c"}, {"a", "b", "c", "d"})  # 3/4 = 0.75
    assert above < DEDUP_SIMILARITY_THRESHOLD
    assert below < DEDUP_SIMILARITY_THRESHOLD
    assert definitely_above > DEDUP_SIMILARITY_THRESHOLD


def test_deduplicate_articles_keeps_first_duplicate_and_unique_entries():
    """Near-duplicate titles should collapse while unique titles remain."""
    now = dt.datetime.now(dt.timezone.utc)
    articles = [
        {
            "title": "Gold prices rally after central bank comments",
            "summary": "Move continues.",
            "link": "a",
            "source": "X",
            "published": now,
        },
        {
            "title": "Gold prices rally after central bank comment",
            "summary": "Move continues strongly.",
            "link": "b",
            "source": "Y",
            "published": now,
        },
        {
            "title": "Natural gas inventories surprise lower",
            "summary": "Different story.",
            "link": "c",
            "source": "Z",
            "published": now,
        },
    ]

    deduped = deduplicate_articles(articles)
    titles = [a["title"] for a in deduped]

    assert "Gold prices rally after central bank comments" in titles
    assert "Natural gas inventories surprise lower" in titles
    assert len(deduped) == 2


def test_score_sentiment_fallback_path(monkeypatch):
    """Keyword fallback should still produce bounded sentiment output."""
    monkeypatch.setattr("pulseengine.core.sentiment.VADER_AVAILABLE", False)
    monkeypatch.setattr("pulseengine.core.sentiment._vader", None)

    s = score_sentiment("surge rally growth profit")
    assert -1.0 <= s["compound"] <= 1.0
    assert s["compound"] > 0


def test_score_sentiment_vader_path(monkeypatch):
    """When VADER is available, score_sentiment should proxy VADER scores."""

    class _FakeVader:
        @staticmethod
        def polarity_scores(_text):
            return {"compound": 0.42, "pos": 0.6, "neg": 0.1, "neu": 0.3}

    monkeypatch.setattr("pulseengine.core.sentiment.VADER_AVAILABLE", True)
    monkeypatch.setattr("pulseengine.core.sentiment._vader", _FakeVader())

    s = score_sentiment("any text")
    assert s["compound"] == 0.42
    assert s["pos"] == 0.6


def test_compute_signal_score_component_behavior_and_clamping(monkeypatch):
    """Extreme weighted components should still clamp total score to [-10, +10]."""
    monkeypatch.setattr(
        "pulseengine.core.signals.ASSET_CLASS_WEIGHTS",
        {
            "Stress": {
                "trend": 5.0,
                "momentum": 5.0,
                "rsi": 5.0,
                "sentiment": 5.0,
                "trend_strength": 5.0,
                "context": 5.0,
            }
        },
    )

    bullish = compute_signal_score(
        metrics={"trend": "uptrend", "change_1d": 3.0},
        momentum={"roc_10d": 50.0, "rsi": 20.0, "trend_strength": 10.0},
        news=[{"sentiment": {"compound": 1.0}}],
        market_ctx={"is_market_wide": True, "is_sector_wide": True},
        category="Stress",
    )
    bearish = compute_signal_score(
        metrics={"trend": "downtrend", "change_1d": -3.0},
        momentum={"roc_10d": -50.0, "rsi": 90.0, "trend_strength": -10.0},
        news=[{"sentiment": {"compound": -1.0}}],
        market_ctx={"is_market_wide": True, "is_sector_wide": True},
        category="Stress",
    )

    assert bullish["score"] == 10.0
    assert bearish["score"] == -10.0


def test_detect_contradictions_each_condition_independently():
    """Each contradiction trigger should remain discoverable."""
    cases = [
        (
            {"change_1d": 3.2, "trend": "sideways"},
            {"rsi": 75.0, "roc_10d": 0.0},
            [],
            {"score": 0.0},
            "overbought_surge",
        ),
        (
            {"change_1d": -3.2, "trend": "sideways"},
            {"rsi": 25.0, "roc_10d": 0.0},
            [],
            {"score": 0.0},
            "oversold_drop",
        ),
        (
            {"change_1d": 1.0, "trend": "uptrend"},
            {"rsi": 50.0, "roc_10d": 0.0},
            [{"type": "sentiment_diverged"}],
            {"score": 0.0},
            "trend_sentiment_conflict",
        ),
        (
            {"change_1d": -1.0, "trend": "downtrend"},
            {"rsi": 50.0, "roc_10d": 0.0},
            [],
            {"score": 4.0},
            "trend_signal_conflict",
        ),
        (
            {"change_1d": 0.5, "trend": "sideways"},
            {"rsi": 50.0, "roc_10d": 11.0},
            [],
            {"score": 0.0},
            "momentum_no_catalyst",
        ),
    ]

    for metrics, momentum, factors, signal, expected_type in cases:
        contradictions = _detect_contradictions(metrics, momentum, factors, signal)
        found_types = {c["type"] for c in contradictions}
        assert expected_type in found_types


def test_correlate_news_accepts_generated_keywords_for_custom_ticker():
    """Custom ticker keywords should enable matching even without curated asset entries."""
    now = dt.datetime.now(dt.timezone.utc)
    articles = [
        {
            "title": "Palantir wins major U.S. defense contract",
            "summary": "AI platform secures multi-year agreement.",
            "link": "https://example.com/pltr",
            "source": "MarketWatch",
            "published": now,
        }
    ]

    without_keywords = correlate_news("PLTR", articles)
    with_keywords = correlate_news("PLTR", articles, keywords=["Palantir", "Alex Karp"])

    assert without_keywords == []
    assert len(with_keywords) == 1
    assert with_keywords[0]["relevance_score"] > 0
