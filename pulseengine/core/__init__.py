"""
pulseengine.core — Headless market intelligence engine.

The core module provides all shared domain logic for market analysis, independent
of any UI surface or storage backend. It consolidates all previously scattered
domain logic from app/, src/, config/, and storage/ into a single cohesive module.

**Design Principles:**
- No surface-specific imports (Streamlit-free)
- Configurable storage paths (no hardcoded assumptions)
- Comprehensive public API with 65+ functions and constants
- Full backward compatibility through re-export shims

**Architectural Layers:**
The v0.3 restructure establishes this foundation for future expansion:
    core       - This module: headless engine (shared by local/ and web/)
    local      - Streamlit dashboard and CLI (future: `local/`)
    web        - Web service wrapper (future: `web/`)

**Public API:**
"""

from __future__ import annotations

# Pipeline orchestration
from .app import (
    STORAGE_AVAILABLE,
    analyse_asset,
    fetch_all_metrics_parallel,
    run_full_scan,
)

# Backtesting
from .backtest import (
    evaluate_all_assets,
    evaluate_signal_accuracy,
    get_signal_streak,
)

# Configuration
from .config import (
    ASSET_CLASS_WEIGHTS,
    ASSET_KEYWORDS,
    BACKTEST_WINDOW,
    BASE_DIR,
    DASHBOARD_ICON,
    DASHBOARD_LAYOUT,
    DASHBOARD_TITLE,
    DEDUP_SIMILARITY_THRESHOLD,
    DEFAULT_CATEGORY,
    EVENT_TRIGGERS,
    LOOKBACK_DAYS,
    MARKET_BENCHMARK,
    MAX_RETRIES,
    MAX_WORKERS,
    MOMENTUM_PERIOD,
    NEWS_FEEDS,
    NEWS_MAX_AGE_HOURS,
    NEWS_MAX_ARTICLES,
    PRICE_CHANGE_THRESHOLD,
    PRICE_FETCH_WORKERS,
    RELEVANCE_HIGH,
    RELEVANCE_MEDIUM,
    RSI_PERIOD,
    SECTOR_PEERS,
    SIGNAL_THRESHOLDS,
    SNAPSHOT_LOAD_LIMIT,
    SOURCE_WEIGHTS,
    STORAGE_DIR,
    STORAGE_FULL_DETAIL_DAYS,
    STORAGE_MAX_DAYS,
    STORAGE_REDUCED_DETAIL_DAYS,
    TRACKED_ASSETS,
    YFINANCE_BACKOFF_BASE,
    YFINANCE_REQUEST_DELAY,
)

# Context
from .context import (
    analyse_market_context,
    find_category,
)

# Errors
from .errors import (
    DataFetchError,
    PipelineError,
    SignalComputationError,
    StorageError,
)

# Explanation
from .explanation import (
    build_explanation,
)

# News
from .news import (
    cluster_articles,
    deduplicate_articles,
    fetch_news_articles,
    generate_keywords,
    get_display_clusters,
)

# Price
from .price import (
    classify_trend,
    compute_momentum_metrics,
    compute_price_metrics,
    compute_roc,
    compute_rsi,
    fetch_price_history,
)

# Sentiment
from .sentiment import (
    FINANCE_LEXICON,
    VADER_AVAILABLE,
    score_sentiment,
)

# Signals
from .signals import (
    compute_signal_score,
    correlate_news,
    detect_events,
)

# Storage
from .storage import (
    apply_retention_policy,
    cleanup_old_snapshots,
    get_historical_features,
    list_tracked_assets_with_history,
    load_recent_snapshots,
    load_snapshots,
    save_snapshot,
)

__all__ = [
    # Config
    "ASSET_CLASS_WEIGHTS",
    "ASSET_KEYWORDS",
    "BACKTEST_WINDOW",
    "BASE_DIR",
    "DASHBOARD_ICON",
    "DASHBOARD_LAYOUT",
    "DASHBOARD_TITLE",
    "DEDUP_SIMILARITY_THRESHOLD",
    "DEFAULT_CATEGORY",
    "EVENT_TRIGGERS",
    "LOOKBACK_DAYS",
    "MARKET_BENCHMARK",
    "MAX_RETRIES",
    "MAX_WORKERS",
    "MOMENTUM_PERIOD",
    "NEWS_FEEDS",
    "NEWS_MAX_AGE_HOURS",
    "NEWS_MAX_ARTICLES",
    "PRICE_CHANGE_THRESHOLD",
    "PRICE_FETCH_WORKERS",
    "RELEVANCE_HIGH",
    "RELEVANCE_MEDIUM",
    "RSI_PERIOD",
    "SECTOR_PEERS",
    "SIGNAL_THRESHOLDS",
    "SNAPSHOT_LOAD_LIMIT",
    "SOURCE_WEIGHTS",
    "STORAGE_DIR",
    "STORAGE_FULL_DETAIL_DAYS",
    "STORAGE_MAX_DAYS",
    "STORAGE_REDUCED_DETAIL_DAYS",
    "TRACKED_ASSETS",
    "YFINANCE_BACKOFF_BASE",
    "YFINANCE_REQUEST_DELAY",
    # Errors
    "DataFetchError",
    "PipelineError",
    "SignalComputationError",
    "StorageError",
    # Price
    "classify_trend",
    "compute_momentum_metrics",
    "compute_price_metrics",
    "compute_roc",
    "compute_rsi",
    "fetch_price_history",
    # News
    "cluster_articles",
    "deduplicate_articles",
    "fetch_news_articles",
    "generate_keywords",
    "get_display_clusters",
    # Sentiment
    "FINANCE_LEXICON",
    "VADER_AVAILABLE",
    "score_sentiment",
    # Signals
    "compute_signal_score",
    "correlate_news",
    "detect_events",
    # Context
    "analyse_market_context",
    "find_category",
    # Explanation
    "build_explanation",
    # App
    "STORAGE_AVAILABLE",
    "analyse_asset",
    "fetch_all_metrics_parallel",
    "run_full_scan",
    # Storage
    "apply_retention_policy",
    "cleanup_old_snapshots",
    "get_historical_features",
    "load_recent_snapshots",
    "load_snapshots",
    "list_tracked_assets_with_history",
    "save_snapshot",
    # Backtest
    "evaluate_all_assets",
    "evaluate_signal_accuracy",
    "get_signal_streak",
]
