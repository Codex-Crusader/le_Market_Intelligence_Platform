"""
app/analysis.py — Backward-compatible re-export shim.

All domain logic now lives in pulseengine.core/. This file re-exports every name
for backward compatibility with existing code (dashboard.py, scan.py, tests).

New code should import directly from pulseengine.core.
"""

import logging

# ── Re-exports from pulseengine.core ──────────────────────────────────────────

from pulseengine.core import (  # noqa:F401
    # Price
    fetch_price_history,
    compute_price_metrics,
    compute_momentum_metrics,
    compute_rsi,
    compute_roc,
    classify_trend,
    # Sentiment
    VADER_AVAILABLE,
    score_sentiment,
    FINANCE_LEXICON,
    # News
    fetch_news_articles,
    deduplicate_articles,
    cluster_articles,
    get_display_clusters,
    generate_keywords,
    # Signals
    correlate_news,
    detect_events,
    compute_signal_score,
    # Context
    analyse_market_context,
    find_category,
    # Explanation
    build_explanation,
    # Errors
    DataFetchError,
    PipelineError,
    SignalComputationError,
    StorageError,
    # App
    analyse_asset,
    run_full_scan,
    fetch_all_metrics_parallel,
    STORAGE_AVAILABLE,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)

# Backward-compat aliases retained for older imports and tests.
_compute_rsi = compute_rsi
_compute_roc = compute_roc

# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    from pulseengine.core import TRACKED_ASSETS

    print("=" * 60)
    print("  PulseEngine — CLI Test")
    print("=" * 60)
    print(f"VADER available:   {VADER_AVAILABLE}")
    print(f"Storage available: {STORAGE_AVAILABLE}")

    _articles = fetch_news_articles()
    print(f"Fetched {len(_articles)} articles\n")

    first_cat   = list(TRACKED_ASSETS.keys())[0]
    first_asset = list(TRACKED_ASSETS[first_cat].keys())[0]
    first_tick  = TRACKED_ASSETS[first_cat][first_asset]

    result = analyse_asset(
        first_asset, first_tick, first_cat, _articles, with_market_ctx=False
    )
    print(result["explanation"]["verdict"])
    print()
    print(f"Signal: {result['signal']['label']} ({result['signal']['score']:+.1f})")
    print()
    print(f"Why it matters: {result['explanation']['why_it_matters']}")
    print()
    print(result["explanation"]["detail"][:800])
