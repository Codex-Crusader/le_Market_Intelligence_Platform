"""
src/price.py — Price data fetching and technical metrics.

Single responsibility: everything that touches Yahoo Finance price data.

Pipeline role (steps 1 and 1.5 of the full engine):
  - fetch_price_history   : download OHLCV from Yahoo Finance with retry/backoff
  - compute_price_metrics : derive change, volatility, trend label from a DataFrame
  - compute_momentum_metrics : RSI, rate-of-change, trend strength, momentum acceleration
"""

from __future__ import annotations

import datetime as dt
import logging
import math
import tempfile
import threading
import time

import pandas as pd
import yfinance as yf

from .config import (
    LOOKBACK_DAYS,
    MAX_RETRIES,
    MOMENTUM_PERIOD,
    PRICE_FETCH_WORKERS,
    REQUEST_TIMEOUT,
    RSI_PERIOD,
    YFINANCE_BACKOFF_BASE,
    YFINANCE_REQUEST_DELAY,
)
from .errors import DataFetchError

# Redirect yfinance TZ cache to the system temp dir to avoid permission errors
# on read-only or cloud deployments (e.g. Streamlit Cloud, Docker)
yf.set_tz_cache_location(tempfile.gettempdir())

log = logging.getLogger(__name__)

# Semaphore: only PRICE_FETCH_WORKERS callers enter Yahoo Finance at a time.
_yf_semaphore = threading.Semaphore(PRICE_FETCH_WORKERS)


# ── Fetching ─────────────────────────────────────────────────────────────────

def fetch_price_history(
    ticker: str,
    days: int = LOOKBACK_DAYS,
) -> pd.DataFrame | None:
    """Download OHLCV history for *ticker*.

    Returns None when the market simply has no data for the requested window.
    Raises DataFetchError when the fetch itself fails after retries.
    """
    end   = dt.datetime.now()
    start = end - dt.timedelta(days=days)
    last_error: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with _yf_semaphore:
                data = yf.download(
                    ticker,
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    progress=False,
                    timeout=REQUEST_TIMEOUT,
                )
            # Sleep after releasing the semaphore so the slot is free for other
            # workers while this thread waits — holding it during sleep blocked
            # all PRICE_FETCH_WORKERS slots for the full delay period.
            time.sleep(YFINANCE_REQUEST_DELAY)

            if data is None or data.empty:
                log.warning("Empty data for %s (attempt %d/%d)", ticker, attempt, MAX_RETRIES)
                # yfinance download() fails for some index/futures tickers (KeyError 'chart').
                # Fall back to Ticker.history() which uses a different API endpoint.
                data = _fetch_via_ticker_history(ticker, days)
                if data is None or data.empty:
                    continue

            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            return data

        except Exception as exc:
            last_error = exc
            exc_str = str(exc).lower()
            is_rate_limit = any(k in exc_str for k in ("rate", "429", "too many", "ratelimit"))
            backoff = YFINANCE_BACKOFF_BASE * (2 ** (attempt - 1)) * (3 if is_rate_limit else 1)
            log.error(
                "Fetch error for %s (attempt %d/%d): %s%s",
                ticker, attempt, MAX_RETRIES, exc,
                f" — rate limited, backing off {backoff:.1f}s" if is_rate_limit else "",
            )
            if attempt < MAX_RETRIES:
                # Try the Ticker.history() fallback before sleeping and retrying download().
                data = _fetch_via_ticker_history(ticker, days)
                if data is not None and not data.empty:
                    return data
                time.sleep(backoff)

    if last_error is not None:
        raise DataFetchError(
            f"Unable to fetch price history for {ticker} after {MAX_RETRIES} attempts"
        ) from last_error
    return None


def _fetch_via_ticker_history(ticker: str, days: int) -> pd.DataFrame | None:
    """
    Fallback fetcher using yf.Ticker.history().

    yf.download() internally calls the 'chart' endpoint which occasionally
    returns a malformed response for certain index tickers (e.g. ^VIX).
    Ticker.history() uses the v8 finance endpoint and is more resilient.
    Uses explicit start/end dates — Ticker.history(period=) only accepts a
    fixed set of strings ("1mo", "3mo", …) and silently returns empty data
    for anything else.
    """
    try:
        end   = dt.datetime.now()
        start = end - dt.timedelta(days=days)
        with _yf_semaphore:
            data = yf.Ticker(ticker).history(
                start=start.strftime("%Y-%m-%d"),
                end=end.strftime("%Y-%m-%d"),
                timeout=REQUEST_TIMEOUT,
            )
        time.sleep(YFINANCE_REQUEST_DELAY)
        if data is None or data.empty:
            return None
        if isinstance(data.columns, pd.MultiIndex):
            data.columns = data.columns.get_level_values(0)
        return data
    except Exception as exc:
        log.warning("Ticker.history() fallback failed for %s: %s", ticker, exc)
        return None


# ── Price metrics ────────────────────────────────────────────────────────────

def compute_price_metrics(df: pd.DataFrame | None) -> dict:
    """Return a dict of price analytics derived from a price DataFrame."""
    if df is None or df.empty:
        return {}

    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    if not isinstance(close, pd.Series):
        close = pd.Series([float(close)])

    latest = float(close.iloc[-1])
    if not math.isfinite(latest):
        return {}

    def safe_pct(n: int) -> float | None:
        if len(close) > n:
            old = float(close.iloc[-(n + 1)])
            if abs(old) < 1e-9 or not math.isfinite(old):
                return None
            pct = ((latest - old) / old) * 100
            return round(pct, 2) if math.isfinite(pct) else None
        return None

    vol = (
        round(float(close.pct_change(fill_method=None).std() * 100), 4)
        if len(close) > 1 else 0.0
    )

    return {
        "latest_price": round(latest, 4),
        "change_1d":    safe_pct(1),
        "change_7d":    safe_pct(7),
        "change_30d":   safe_pct(min(30, len(close) - 1)),
        "high_30d":     round(float(close.max()), 4),
        "low_30d":      round(float(close.min()), 4),
        "volatility":   vol,
        "trend":        classify_trend(close),
    }


def classify_trend(series: pd.Series) -> str:
    """Label the price series as uptrend / downtrend / sideways."""
    if len(series) < 8:
        return "insufficient data"
    ma7    = float(series.rolling(7).mean().iloc[-1])
    window = min(30, len(series))
    ma30   = float(series.rolling(window).mean().iloc[-1])
    if not math.isfinite(ma7) or not math.isfinite(ma30) or ma30 == 0:
        return "sideways"
    if ma7 > ma30 * 1.01:
        return "uptrend"
    if ma7 < ma30 * 0.99:
        return "downtrend"
    return "sideways"


# ── Momentum metrics ─────────────────────────────────────────────────────────

def compute_momentum_metrics(df: pd.DataFrame | None) -> dict:
    """
    Return RSI, rate-of-change, trend strength, and momentum acceleration.
    Falls back to neutral defaults when data is insufficient.
    """
    defaults = {"rsi": 50.0, "roc_10d": 0.0, "trend_strength": 0.0, "momentum_accel": 0.0}
    if df is None or df.empty:
        return defaults

    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    close = close.dropna()

    if len(close) < 2:
        return defaults

    rsi = compute_rsi(close, RSI_PERIOD)
    roc = compute_roc(close, MOMENTUM_PERIOD)

    # Trend strength: how far the 7-day MA is from the long-term MA (%)
    trend_strength = 0.0
    window = min(30, len(close))
    if len(close) >= 7:
        ma7    = float(close.rolling(7).mean().iloc[-1])
        ma_ref = float(close.rolling(window).mean().iloc[-1])
        if ma_ref != 0 and math.isfinite(ma7) and math.isfinite(ma_ref):
            ts = ((ma7 - ma_ref) / ma_ref) * 100
            trend_strength = round(ts, 2) if math.isfinite(ts) else 0.0

    # Momentum acceleration: derivative of rate-of-change
    momentum_accel = 0.0
    if len(close) > 10:
        recent_roc = compute_roc(close.iloc[-6:], 5)
        prior_roc  = compute_roc(close.iloc[-11:-5], 5) if len(close) >= 11 else 0.0
        momentum_accel = round(recent_roc - prior_roc, 2)

    return {
        "rsi":            rsi,
        "roc_10d":        roc,
        "trend_strength": trend_strength,
        "momentum_accel": momentum_accel,
    }


def compute_rsi(series: pd.Series, period: int = 14) -> float:
    """Compute Wilder RSI. Returns 50.0 when there is insufficient data."""
    if len(series) < period + 1:
        return 50.0
    delta    = series.diff().dropna()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean().iloc[-1]
    avg_loss = loss.rolling(period).mean().iloc[-1]
    if pd.isna(avg_gain) or pd.isna(avg_loss):
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(float(100 - (100 / (1 + rs))), 1)


def compute_roc(series: pd.Series, period: int = 10) -> float:
    """Rate of change over *period* bars, expressed as a percentage."""
    if len(series) <= period:
        return 0.0
    old = float(series.iloc[-(period + 1)])
    new = float(series.iloc[-1])
    if abs(old) < 1e-9 or not math.isfinite(old) or not math.isfinite(new):
        return 0.0
    roc = ((new - old) / old) * 100
    return round(roc, 2) if math.isfinite(roc) else 0.0

