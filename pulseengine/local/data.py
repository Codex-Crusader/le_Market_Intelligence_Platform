"""
data.py — Cached data loaders and staleness helpers for the local dashboard.

All st.cache_data functions live here so dashboard.py stays free of caching
boilerplate.  Heavy computation (scan, metrics) remains in scan.py / pulseengine.core.
"""

from __future__ import annotations

import datetime as dt
import logging

import pandas as pd
import streamlit as st

from pulseengine.core.config import NEWS_CACHE_TTL, PRICE_CACHE_TTL, SCAN_INTERVAL_MINUTES
from pulseengine.core import fetch_news_articles, fetch_price_history, generate_keywords
from pulseengine.local.scan import load_last_scan_summary

log = logging.getLogger(__name__)


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


@st.cache_data(ttl=SCAN_INTERVAL_MINUTES * 60)
def cached_scan_summary(cache_token: int = 0) -> dict:
    """Load the latest scan summary from disk — no network calls."""
    _ = cache_token  # cache-buster only; kept out of the return value on purpose
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
