"""
src/context.py — Market and sector context analysis.

Single responsibility: determine whether an asset move is asset-specific,
sector-wide, or market-wide by comparing it against sector peers and a
broad market benchmark.

Pipeline role (step 6 of the full engine):
  - analyse_market_context : fetch peer and benchmark prices, classify the move
  - find_category          : resolve an asset name to its config category
  - _find_ticker           : internal helper to look up a ticker from TRACKED_ASSETS

Price cache
-----------
analyse_market_context accepts an optional ``price_cache`` mapping of
``{ticker: change_1d}``.  When a peer or benchmark ticker is present in the
cache the network fetch is skipped entirely — this eliminates the ~50-80
redundant yfinance calls that occur during a full-market batch scan where the
same tickers appear as peers for multiple assets.

Pass ``price_cache=None`` (the default) to retain the original fetch-on-demand
behaviour (used by the dashboard for on-demand single-asset analysis).
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

from .config import (
    MARKET_BENCHMARK,
    PRICE_FETCH_WORKERS,
    SECTOR_PEERS,
    TRACKED_ASSETS,
)
from .errors import DataFetchError
from .price import fetch_price_history, compute_price_metrics

log = logging.getLogger(__name__)


def analyse_market_context(
    asset_name: str,
    category: str,
    asset_change: float | None,
    price_cache: dict[str, float] | None = None,
) -> dict:
    """
    Compare the asset's move against sector peers and the broad market
    benchmark to determine whether the move is asset-specific or systemic.

    Parameters
    ----------
    asset_name   : name of the asset being analysed
    category     : asset class (used to look up the benchmark ticker)
    asset_change : today's price change % for the asset
    price_cache  : optional {ticker: change_1d} dict built before the scan loop.
                   When a ticker is present in the cache its change_1d is used
                   directly and no network call is made.  Pass None to always fetch.

    Returns a dict with keys:
      peer_moves        — {peer_name: change_1d}
      benchmark_change  — float or None
      is_sector_wide    — bool (>= 60 % of peers moved in same direction)
      is_market_wide    — bool (benchmark moved same direction by > 0.5 %)
      is_asset_specific — bool (neither sector nor market wide)
    """
    context: dict = {
        "peer_moves":        {},
        "peer_errors":       {},
        "benchmark_change":  None,
        "benchmark_error":   None,
        "is_sector_wide":    False,
        "is_market_wide":    False,
        "is_asset_specific": False,
    }

    if asset_change is None:
        return context

    direction = 1 if asset_change > 0 else -1

    # ── Peer comparison (parallel) ───────────────────────────────────────────
    peers = SECTOR_PEERS.get(asset_name, [])
    peer_data: dict[str, float | None] = {}
    peer_errors: dict[str, dict] = {}

    def _fetch_peer(peer_name: str) -> tuple[str, float | None, dict | None]:
        peer_ticker = _find_ticker(peer_name)
        if not peer_ticker:
            return peer_name, None, None
        # Use pre-built cache when available — skips a network round-trip
        if price_cache is not None and peer_ticker in price_cache:
            return peer_name, price_cache[peer_ticker], None
        try:
            peer_hist = fetch_price_history(peer_ticker, days=5)
        except DataFetchError as _peer_exc:
            return peer_name, None, {
                "type": "data_fetch_error",
                "stage": "peer_price_history",
                "peer": peer_name,
                "ticker": peer_ticker,
                "message": str(_peer_exc),
            }
        if peer_hist is None or peer_hist.empty:
            return peer_name, None, None
        peer_m = compute_price_metrics(peer_hist)
        return peer_name, peer_m.get("change_1d"), None

    if peers:
        with ThreadPoolExecutor(max_workers=min(len(peers), PRICE_FETCH_WORKERS)) as ex:
            for name, chg, err in ex.map(_fetch_peer, peers):
                peer_data[name] = chg
                if err:
                    peer_errors[name] = err

    same_dir = sum(
        1 for chg in peer_data.values()
        if chg is not None and chg * direction > 0
    )
    context["peer_moves"] = peer_data
    if peer_errors:
        context["peer_errors"] = peer_errors
    if peers and same_dir / max(len(peers), 1) >= 0.6:
        context["is_sector_wide"] = True

    # ── Benchmark comparison ─────────────────────────────────────────────────
    bench_ticker = MARKET_BENCHMARK.get(category)
    if bench_ticker:
        bench_chg: float | None = None
        if price_cache is not None and bench_ticker in price_cache:
            bench_chg = price_cache[bench_ticker]
        else:
            try:
                hist = fetch_price_history(bench_ticker, days=5)
            except DataFetchError as exc:
                context["benchmark_error"] = {
                    "type": "data_fetch_error",
                    "stage": "benchmark_price_history",
                    "ticker": bench_ticker,
                    "message": str(exc),
                }
                hist = None
            if hist is not None and not hist.empty:
                bm        = compute_price_metrics(hist)
                bench_chg = bm.get("change_1d")
        context["benchmark_change"] = bench_chg
        if (
            bench_chg is not None
            and bench_chg * direction > 0
            and abs(bench_chg) > 0.5
        ):
            context["is_market_wide"] = True

    context["is_asset_specific"] = (
        not context["is_sector_wide"] and not context["is_market_wide"]
    )
    return context


# ── Lookup helpers ────────────────────────────────────────────────────────────

# Pre-built O(1) lookup tables derived from the static TRACKED_ASSETS config.
# Iterating the nested dict on every peer lookup added up across 24 assets × ~5
# peers each; a flat dict collapses that to a single hash probe per call.
_TICKER_MAP: dict[str, str] = {
    name: ticker
    for assets in TRACKED_ASSETS.values()
    for name, ticker in assets.items()
}
_CATEGORY_MAP: dict[str, str] = {
    name: cat
    for cat, assets in TRACKED_ASSETS.items()
    for name in assets
}


def _find_ticker(asset_name: str) -> str | None:
    """Return the ticker for *asset_name*."""
    return _TICKER_MAP.get(asset_name)


def find_category(asset_name: str) -> str | None:
    """Return the category string for *asset_name*, or None if not tracked."""
    return _CATEGORY_MAP.get(asset_name)
