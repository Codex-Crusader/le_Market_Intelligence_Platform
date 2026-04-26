"""
data.py — Cached data loaders and staleness helpers for the PulseEngine local dashboard.

All st.cache_data functions live here so dashboard.py stays free of caching
boilerplate.  Heavy computation (scan, metrics) remains in scan.py / core app.
"""

from __future__ import annotations

import datetime as dt
import logging
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pulseengine.core import (
    TRACKED_ASSETS,
    analyse_market_context,
    build_explanation,
    compute_momentum_metrics,
    compute_price_metrics,
    compute_signal_score,
    fetch_news_articles,
    fetch_price_history,
    generate_keywords,
    correlate_news,
)
from pulseengine.core.config import NEWS_CACHE_TTL, PRICE_CACHE_TTL, SCAN_INTERVAL_MINUTES

log = logging.getLogger(__name__)

try:
    from pulseengine.local.scan import load_last_scan_summary
except ImportError:
    log.warning("pulseengine.local.scan could not be imported; load_last_scan_summary will return {}.")
    def load_last_scan_summary() -> dict:  # noqa: E731
        return {}


@st.cache_data(ttl=NEWS_CACHE_TTL, show_spinner="Fetching news feeds ...")
def cached_news() -> list[dict]:
    return fetch_news_articles()


@st.cache_data(ttl=NEWS_CACHE_TTL, show_spinner="Building ticker keywords ...")
def cached_generated_keywords(symbol: str) -> list[str]:
    return generate_keywords(symbol)


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner="Fetching prices ...")
def cached_history(symbol: str) -> pd.DataFrame:
    # Let DataFetchError propagate — st.cache_data does not cache exceptions,
    # so transient network failures retry on the next call instead of being
    # frozen as an empty DataFrame for the full TTL.
    result = fetch_price_history(symbol)
    return result if result is not None else pd.DataFrame()


@st.cache_data(
    ttl=min(NEWS_CACHE_TTL, PRICE_CACHE_TTL),
    show_spinner="Building live analysis ...",
)
def cached_live_analysis(
    asset_name: str,
    ticker: str,
    category: str,
    news_loaded: bool,
    run_context: bool,
    scan_token: int = 0,
    keywords: tuple[str, ...] = (),
    price_cache_items: tuple[tuple[str, float], ...] = (),
) -> dict:
    """Build the live analysis payload for the selected asset.

    The result is cached so reruns from unrelated UI changes reuse the same
    expensive metrics, sentiment, and explanation work until the underlying
    price/news TTLs or scan token change.
    """
    _ = scan_token

    history = cached_history(ticker)
    if history.empty:
        return {
            "error": f"Could not load price data for {asset_name} ({ticker}).",
            "history": history,
            "metrics": {},
            "momentum": {},
            "news": [],
            "clusters": {},
            "market_ctx": None,
            "signal": {"score": 0.0, "label": "No Data"},
            "explanation": {"verdict": "No price data available."},
        }

    articles = cached_news() if news_loaded else []
    live_news = correlate_news(
        asset_name,
        articles,
        keywords=list(keywords) if keywords else None,
    )
    live_metrics = compute_price_metrics(history)
    live_momentum = compute_momentum_metrics(history)

    market_ctx = None
    if (
        run_context
        and category in TRACKED_ASSETS
        and live_metrics.get("change_1d") is not None
    ):
        price_cache = dict(price_cache_items) if price_cache_items else None
        market_ctx = analyse_market_context(
            asset_name,
            category,
            live_metrics["change_1d"],
            price_cache=price_cache,
        )

    live_signal = compute_signal_score(
        live_metrics,
        live_momentum,
        live_news,
        market_ctx,
        category=category,
    )
    live_explanation = build_explanation(
        asset_name,
        live_metrics,
        live_news,
        market_ctx,
        live_momentum,
        live_signal,
    )

    return {
        "error": None,
        "history": history,
        "metrics": live_metrics,
        "momentum": live_momentum,
        "news": live_news,
        "clusters": {},
        "market_ctx": market_ctx,
        "signal": live_signal,
        "explanation": live_explanation,
    }


@st.cache_data(ttl=SCAN_INTERVAL_MINUTES * 60)
def cached_scan_summary(cache_token: int = 0) -> dict:
    """Load the latest scan summary from disk — no network calls."""
    _ = cache_token  # cache-buster only
    return load_last_scan_summary()


def is_data_stale(summary: dict, ttl_hours: float = 1.0) -> bool:
    """Return True if the scan summary is older than *ttl_hours*, or missing."""
    scan_time = summary.get("scan_time")
    if not scan_time:
        return True
    try:
        last = dt.datetime.fromisoformat(scan_time)
        if last.tzinfo is None:
            last = last.replace(tzinfo=dt.timezone.utc)
        return dt.datetime.now(dt.timezone.utc) - last > dt.timedelta(hours=ttl_hours)
    except (ValueError, TypeError):
        return True
