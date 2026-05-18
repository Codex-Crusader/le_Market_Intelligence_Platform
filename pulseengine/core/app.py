"""
pulseengine/core/app.py — Pipeline orchestration.

Single responsibility: coordinate all other modules to produce per-asset
analysis results and drive the full market scan.

Pipeline role (steps 11 and 12 of the full engine):
  - analyse_asset            : run the complete pipeline for a single asset
  - run_full_scan            : run analyse_asset across every tracked asset in parallel
  - fetch_all_metrics_parallel : lightweight parallel price + momentum fetch
                                 (used by the dashboard heatmap / top-movers view)

This module owns no domain logic — it only wires together src/price, src/news,
src/signals, src/context, and src/explanation.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from .config import (
    LOOKBACK_DAYS,
    PRICE_FETCH_WORKERS,
    TRACKED_ASSETS,
)
from .context import analyse_market_context
from .errors import DataFetchError, _build_error_payload
from .explanation import build_explanation
from .news import cluster_articles, fetch_news_articles
from .price import (
    compute_momentum_metrics,
    compute_price_metrics,
    fetch_price_history,
)
from .signals import compute_signal_score, correlate_news

log = logging.getLogger(__name__)


_save_snapshot: Callable[..., Any]
_get_historical_features: Callable[..., Any]

try:
    from .storage import get_historical_features as _get_historical_features
    from .storage import save_snapshot as _save_snapshot
    STORAGE_AVAILABLE = True
except ImportError:
    STORAGE_AVAILABLE = False
    def _save_snapshot(*_a: Any, **_kw: Any) -> None: pass           # noqa: E731
    def _get_historical_features(*_a: Any, **_kw: Any) -> dict: return {}  # noqa: E731


# ── Single-asset analysis ─────────────────────────────────────────────────────

def analyse_asset(
    asset_name: str,
    ticker: str,
    category: str,
    articles: list[dict],
    with_market_ctx: bool = False,
    save: bool = False,
    price_cache: dict[str, float] | None = None,
) -> dict:
    """Run the full analysis pipeline for a single asset.

    Parameters
    ----------
    asset_name      : human-readable asset name (e.g. ``"Gold"``)
    ticker          : Yahoo Finance ticker symbol (e.g. ``"GC=F"``)
    category        : asset class string matching a key in TRACKED_ASSETS
                      (e.g. ``"Commodities"``)
    articles        : deduplicated news article dicts from fetch_news_articles()
    with_market_ctx : when True, runs analyse_market_context() to classify the
                      move as asset-specific, sector-wide, or market-wide.
                      Defaults to False for single-asset on-demand calls.
    save            : when True, persists a compressed snapshot via save_snapshot().
                      Should only be True in the batch scan pipeline (scan.py).
    price_cache     : optional ``{ticker: change_1d}`` mapping pre-built before a
                      batch scan.  Passed through to analyse_market_context so peer
                      and benchmark price lookups are served from memory rather than
                      making redundant yfinance calls.  Has no effect when
                      with_market_ctx=False.
    """
    log.info("Analysing %s (%s)", asset_name, ticker)
    history  = None
    fetch_error = None
    try:
        history = fetch_price_history(ticker)
    except DataFetchError as exc:
        fetch_error = _build_error_payload(
            "price_history",
            exc,
            asset=asset_name,
            ticker=ticker,
            category=category,
        )
        log.warning("Price history unavailable for %s (%s): %s", asset_name, ticker, exc)

    metrics  = compute_price_metrics(history)
    momentum = compute_momentum_metrics(history)
    news     = correlate_news(asset_name, articles)
    clusters = cluster_articles(news)

    market_ctx = None
    if with_market_ctx and metrics.get("change_1d") is not None:
        market_ctx = analyse_market_context(
            asset_name, category, metrics["change_1d"], price_cache=price_cache
        )

    signal      = compute_signal_score(metrics, momentum, news, market_ctx, category=category)
    explanation = build_explanation(
        asset_name, metrics, news, market_ctx, momentum, signal
    )

    # Only the batch pipeline should persist snapshots — dashboard stays read-only
    if save and STORAGE_AVAILABLE and fetch_error is None and metrics:
        try:
            _save_snapshot(asset_name, metrics, momentum, signal, news[:5], market_ctx=market_ctx)
        except Exception as exc:
            log.warning("Snapshot not saved for %s: %s", asset_name, exc)

    historical_features: dict = {}
    if STORAGE_AVAILABLE:
        try:
            historical_features = _get_historical_features(asset_name)
        except Exception as exc:
            log.warning("Historical features unavailable for %s: %s", asset_name, exc)

    return {
        "ticker":              ticker,
        "history":             history,
        "metrics":             metrics,
        "momentum":            momentum,
        "news":                news,
        "clusters":            clusters,
        "market_ctx":          market_ctx,
        "signal":              signal,
        "explanation":         explanation,
        "historical_features": historical_features,
        "error":               fetch_error,
    }


# ── Parallel price/momentum fetch (dashboard helper) ──────────────────────────

def _fetch_one_asset(cat: str, name: str, tkr: str, days: int) -> tuple:
    """Worker used by fetch_all_metrics_parallel — module-level to avoid closure shadowing."""
    hist         = fetch_price_history(tkr, days=days)
    metrics_data = compute_price_metrics(hist)
    mom_data     = compute_momentum_metrics(hist)
    return cat, name, metrics_data, mom_data


def fetch_all_metrics_parallel(days: int = LOOKBACK_DAYS) -> dict:
    """
    Fetch price metrics and momentum for every tracked asset in parallel.

    Returns {category: {asset_name: {metrics: ..., momentum: ...}}}.
    Used by the dashboard for heatmaps and top-mover views.
    """
    all_results: dict = {}
    all_assets = [
        (cat, name, tkr)
        for cat, assets in TRACKED_ASSETS.items()
        for name, tkr in assets.items()
    ]

    with ThreadPoolExecutor(max_workers=PRICE_FETCH_WORKERS) as ex:
        futures = {
            ex.submit(_fetch_one_asset, cat, name, tkr, days): (cat, name)
            for cat, name, tkr in all_assets
        }
        for future in as_completed(futures):
            try:
                f_cat, f_name, f_metrics, f_mom = future.result()
                all_results.setdefault(f_cat, {})[f_name] = {
                    "metrics":  f_metrics,
                    "momentum": f_mom,
                }
            except Exception as exc:
                log.warning("Parallel fetch failed: %s", exc)

    return all_results


# ── Full market scan ──────────────────────────────────────────────────────────

def run_full_scan() -> dict:
    """Run the complete pipeline across every tracked asset in parallel.

    **Dashboard helper — does not persist snapshots.**

    This function is called by the Streamlit dashboard background daemon thread
    to populate live in-memory state.  It returns the full rich result objects
    (history DataFrames, article lists, cluster dicts) that the dashboard UI
    needs but which are too large to compress and store.

    Responsibility boundary
    -----------------------
    - run_full_scan() (this function) — dashboard background scan; returns rich
      live objects; no files written; called from dashboard/main.py.
    - app/scan.py :: run_scan()       — batch persistence pipeline; writes
      per-asset .json.gz snapshots and the _scan_summary.json.gz; called from
      the CLI or as a scheduled job.  Uses a pre-built price cache and
      with_market_ctx=True so context flags are persisted in every snapshot.

    Do not add save=True here.  Snapshot writes belong exclusively in run_scan().
    """
    log.info("Starting full market scan ...")
    articles = fetch_news_articles()
    results: dict = {}
    errors: list[dict] = []

    all_tasks = [
        (name, ticker, category)
        for category, assets in TRACKED_ASSETS.items()
        for name, ticker in assets.items()
    ]

    def _run(name: str, ticker: str, category: str) -> tuple:
        return (
            category,
            name,
            analyse_asset(name, ticker, category, articles, with_market_ctx=True),
        )

    with ThreadPoolExecutor(max_workers=PRICE_FETCH_WORKERS) as ex:
        futures = {
            ex.submit(_run, name, tkr, cat): (cat, name)
            for name, tkr, cat in all_tasks
        }
        for future in as_completed(futures):
            try:
                cat, name, res = future.result()
                error = res.get("error") if isinstance(res, dict) else None
                if error:
                    errors.append({**error, "asset": name, "category": cat})
                results.setdefault(cat, {})[name] = res
            except Exception as exc:
                cat, name = futures[future]
                error = _build_error_payload(
                    "full_scan",
                    exc,
                    asset=name,
                    category=cat,
                )
                errors.append(error)
                results.setdefault(cat, {})[name] = {
                    "ticker": TRACKED_ASSETS.get(cat, {}).get(name, ""),
                    "history": None,
                    "metrics": {},
                    "momentum": {},
                    "news": [],
                    "clusters": {},
                    "market_ctx": None,
                    "signal": {"score": None, "label": "Error", "components": {}, "raw_components": {}},
                    "explanation": {
                        "verdict": "",
                        "factors": [],
                        "detail": "",
                        "confidence": "none",
                        "confidence_info": {"level": "none", "score": 0, "reasons": []},
                        "contradictions": [],
                        "why_it_matters": "",
                    },
                    "historical_features": {},
                    "error": error,
                }
                log.error("Analysis error for %s (%s): %s", name, cat, exc)

    log.info("Full scan complete.")
    return results
