"""
test_core.py — Sanity and invariant tests for pure functions.

Goal: each function runs without crashing and its output is sane.
Not testing exact values — testing that outputs are usable.
"""

from __future__ import annotations

import datetime as dt
from types import SimpleNamespace

import pandas as pd
import pytest

from pulseengine.core import (
    DataFetchError,
    compute_momentum_metrics,
    compute_price_metrics,
    compute_roc,
    compute_rsi,
    compute_signal_score,
    correlate_news,
    deduplicate_articles,
    fetch_news_articles,
    fetch_price_history,
    generate_keywords,
    score_sentiment,
)

# Aliases retained so test function names stay meaningful
src_score_sentiment = score_sentiment
src_signal_score    = compute_signal_score
src_dedup           = deduplicate_articles


# ── RSI ───────────────────────────────────────────────────────────────────────

def test_rsi_always_in_range(price_series_rising, price_series_falling, price_series_flat):
    """INVARIANT: RSI must always be between 0 and 100, no matter what."""
    for series in [price_series_rising, price_series_falling, price_series_flat]:
        result = compute_rsi(series)
        assert 0.0 <= result <= 100.0


def test_rsi_direction(price_series_rising, price_series_falling):
    """Rising series → RSI above 50. Falling → RSI below 50."""
    assert compute_rsi(price_series_rising) > 50
    assert compute_rsi(price_series_falling) < 50


# ── ROC ───────────────────────────────────────────────────────────────────────

def test_roc_sign(price_series_rising, price_series_falling):
    """ROC should be positive for an uptrend and negative for a downtrend."""
    assert compute_roc(price_series_rising) > 0
    assert compute_roc(price_series_falling) < 0


# ── Momentum metrics ──────────────────────────────────────────────────────────

def test_momentum_metrics_runs(ohlcv_df, price_series_rising):
    """compute_momentum_metrics should return a dict with a 'rsi' key."""
    result = compute_momentum_metrics(ohlcv_df(price_series_rising))
    assert isinstance(result, dict)
    assert "rsi" in result


# ── Price metrics ─────────────────────────────────────────────────────────────

def test_price_metrics_runs(ohlcv_df, price_series_rising):
    """compute_price_metrics should return a dict with a usable latest_price."""
    result = compute_price_metrics(ohlcv_df(price_series_rising))
    assert isinstance(result, dict)
    assert result.get("latest_price") is not None
    assert result["latest_price"] > 0


# ── Signal score ──────────────────────────────────────────────────────────────

def test_signal_score_in_range(synthetic_metrics, synthetic_momentum):
    """INVARIANT: score must always be clamped to [-10, 10]."""
    result = compute_signal_score(synthetic_metrics, synthetic_momentum, [])
    assert -10.0 <= result["score"] <= 10.0


def test_src_signal_score_in_range(synthetic_metrics, synthetic_momentum):
    """Same invariant via the canonical pulseengine.core import."""
    result = src_signal_score(synthetic_metrics, synthetic_momentum, [])
    assert -10.0 <= result["score"] <= 10.0


def test_low_news_confidence_reduces_sentiment_weight():
    """Low article counts should be flagged and dampen sentiment contribution."""
    metrics = {"trend": "sideways", "change_1d": 0.0}
    momentum = {"roc_10d": 0.0, "rsi": 50.0, "trend_strength": 0.0}

    low_news = [{"sentiment": {"compound": 0.5}}]
    high_news = [
        {"sentiment": {"compound": 0.5}},
        {"sentiment": {"compound": 0.5}},
        {"sentiment": {"compound": 0.5}},
    ]

    low = src_signal_score(metrics, momentum, low_news)
    high = src_signal_score(metrics, momentum, high_news)

    assert low["low_news_confidence"] is True
    assert low["news_article_count"] == 1

    assert high["low_news_confidence"] is False
    assert high["news_article_count"] == 3
    assert low["components"]["sentiment"] < high["components"]["sentiment"]


# ── Sentiment ─────────────────────────────────────────────────────────────────

def test_sentiment_compound_in_range():
    """INVARIANT: sentiment compound must always be in [-1, 1]."""
    result = score_sentiment("markets are crashing hard, major losses everywhere")
    assert -1.0 <= result["compound"] <= 1.0


def test_src_sentiment_compound_in_range():
    """Same invariant via the canonical pulseengine.core import."""
    result = src_score_sentiment("markets are crashing hard, major losses everywhere")
    assert -1.0 <= result["compound"] <= 1.0


# ── Deduplication ─────────────────────────────────────────────────────────────

def test_dedup_reduces_or_preserves_count(synthetic_articles):
    """Dedup should never produce more articles than it received."""
    result = deduplicate_articles(synthetic_articles)
    assert 0 < len(result) <= len(synthetic_articles)


def test_src_dedup_reduces_or_preserves_count(synthetic_articles):
    """Same invariant via the canonical pulseengine.core import."""
    result = src_dedup(synthetic_articles)
    assert 0 < len(result) <= len(synthetic_articles)


# ── Fetch resilience ────────────────────────────────────────────────────────

def test_fetch_price_history_returns_none_for_empty_data(mocker):
    """Empty responses should stay empty rather than becoming fetch errors."""
    mocker.patch("pulseengine.core.price.MAX_RETRIES", 1)
    mocker.patch("pulseengine.core.price.time.sleep", return_value=None)
    mocker.patch("pulseengine.core.price.yf.download", return_value=pd.DataFrame())
    ticker_mock = mocker.Mock()
    ticker_mock.history.return_value = pd.DataFrame()
    mocker.patch("pulseengine.core.price.yf.Ticker", return_value=ticker_mock)

    result = fetch_price_history("TEST", days=1)
    assert result is None


def test_fetch_price_history_raises_on_fetch_failure(mocker):
    """Transport failures should raise a fetch error after retries."""
    mocker.patch("pulseengine.core.price.MAX_RETRIES", 1)
    mocker.patch("pulseengine.core.price.time.sleep", return_value=None)
    mocker.patch("pulseengine.core.price.yf.download", side_effect=RuntimeError("boom"))
    ticker_mock = mocker.Mock()
    ticker_mock.history.side_effect = RuntimeError("boom")
    mocker.patch("pulseengine.core.price.yf.Ticker", return_value=ticker_mock)

    with pytest.raises(DataFetchError):
        fetch_price_history("TEST", days=1)


# ── generate_keywords ─────────────────────────────────────────────────────────

def test_generate_keywords_known_ticker(mocker):
    """Known ticker returns symbol, company name tokens, and officer surnames — not sector/industry."""
    mock_info = {
        "longName": "NVIDIA Corporation",
        "shortName": "NVIDIA",
        "symbol": "NVDA",
        "industry": "Semiconductors",
        "sector": "Technology",
        "companyOfficers": [
            {"name": "Jensen Huang"},
            {"name": "Colette Kress"},
        ],
    }
    ticker_mock = mocker.Mock()
    ticker_mock.info = mock_info
    mocker.patch("pulseengine.core.news.yf.Ticker", return_value=ticker_mock)

    result = generate_keywords("NVDA")
    assert "NVDA" in result
    assert "NVIDIA" in result
    assert "Huang" in result                  # executive surname included
    assert "Semiconductors" not in result     # industry dropped — too broad for keyword matching
    assert "Technology" not in result         # sector dropped — too broad for keyword matching
    assert all(len(kw) >= 3 for kw in result)
    assert len(result) == len({kw.lower() for kw in result}), "result must be deduplicated"


def test_generate_keywords_unknown_ticker(mocker):
    """Unknown ticker (empty info) should return [ticker] without raising."""
    ticker_mock = mocker.Mock()
    ticker_mock.info = {}
    mocker.patch("pulseengine.core.news.yf.Ticker", return_value=ticker_mock)

    result = generate_keywords("NOTREAL")
    assert result == ["NOTREAL"]


def test_generate_keywords_network_failure(mocker):
    """Network failure should return [ticker] without raising."""
    mocker.patch("pulseengine.core.news.yf.Ticker", side_effect=Exception("connection refused"))

    result = generate_keywords("NVDA")
    assert result == ["NVDA"]


def test_generate_keywords_timeout(mocker):
    """When the fetch thread does not finish within REQUEST_TIMEOUT, return [ticker]."""
    thread_mock = mocker.MagicMock()
    thread_mock.is_alive.return_value = True   # simulates a hung thread
    mocker.patch("pulseengine.core.news.threading.Thread", return_value=thread_mock)

    result = generate_keywords("NVDA")
    assert result == ["NVDA"]
    thread_mock.start.assert_called_once()
    thread_mock.join.assert_called_once()


# ── correlate_news word-boundary matching ─────────────────────────────────────

def test_correlate_news_no_substring_false_positive():
    """'gold' keyword must not match articles whose only hit is a substring like 'goldman'."""
    now = dt.datetime.now(dt.timezone.utc)
    goldman_article = {
        "title": "goldman sachs raises forecast for major banks",
        "summary": "Goldman Sachs analysts upgraded their outlook for the banking sector.",
        "link": "https://example.com/gs",
        "source": "Reuters Business",
        "published": now - dt.timedelta(hours=1),
    }
    gold_article = {
        "title": "gold prices hit record as safe haven demand surges",
        "summary": "Bullion climbs on central bank buying.",
        "link": "https://example.com/gold",
        "source": "Reuters Business",
        "published": now - dt.timedelta(hours=1),
    }

    results = correlate_news("Gold", [goldman_article, gold_article])
    matched_titles = {a["title"] for a in results}

    assert goldman_article["title"] not in matched_titles, (
        "Goldman Sachs article must not match Gold — 'gold' is a substring of 'goldman'"
    )
    assert gold_article["title"] in matched_titles, (
        "Gold article must match Gold"
    )


def test_fetch_news_articles_uses_explicit_timeout(mocker):
    """RSS fetches should be bounded by an explicit timeout."""
    mocker.patch("pulseengine.core.news.NEWS_FEEDS", [("Test Feed", "https://example.com/feed")])
    mocker.patch("pulseengine.core.news.MAX_WORKERS", 1)

    response = mocker.MagicMock()
    response.read.return_value = b"<rss />"
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    urlopen_mock = mocker.patch("pulseengine.core.news.urllib.request.urlopen", return_value=response)
    mocker.patch(
        "pulseengine.core.news.feedparser.parse",
        return_value=SimpleNamespace(entries=[]),
    )

    fetch_news_articles()
    assert urlopen_mock.call_args.kwargs["timeout"] > 0
