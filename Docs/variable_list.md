# Variable and Constant Reference

[![Source: pulseengine/core/config.py](https://img.shields.io/badge/Source-pulseengine/core/config.py-64748b?style=flat-square)]()
[![Source: pulseengine/core/app.py](https://img.shields.io/badge/Source-pulseengine/core/app.py-3776AB?style=flat-square)]()
[![Source: pulseengine/local/dashboard.py](https://img.shields.io/badge/Source-pulseengine/local/dashboard.py-FF4B4B?style=flat-square)]()
[![Source: pulseengine/core/storage.py](https://img.shields.io/badge/Source-pulseengine/core/storage.py-f59e0b?style=flat-square)]()
[![Source: pulseengine/local/scan.py](https://img.shields.io/badge/Source-pulseengine/local/scan.py-22c55e?style=flat-square)]()
[![Source: pulseengine/core/backtest.py](https://img.shields.io/badge/Source-pulseengine/core/backtest.py-7c3aed?style=flat-square)]()

This document lists every significant constant, module-level variable, function parameter, and return structure across the codebase. Types follow Python annotation conventions.

> **Module paths** refer to canonical locations in `pulseengine/`. Legacy shim packages (`app/`, `dashboard/`, `config/`, `storage/`) re-export from these canonical paths and remain functional for backward compatibility.

---

## pulseengine/core/config.py — All Constants

### 1. Asset Configuration

| Name | Type | Value / Shape | Description |
|---|---|---|---|
| `TRACKED_ASSETS` | `dict[str, dict[str, str]]` | 4 categories, 24 assets | Top-level map from category name to `{asset_name: yahoo_ticker}`. The only place tickers are defined. |
| `SECTOR_PEERS` | `dict[str, list[str]]` | 22 keys | Maps each asset name to a list of peer asset names used for sector correlation in `analyse_market_context`. |
| `MARKET_BENCHMARK` | `dict[str, str]` | 4 keys | Maps each category to a benchmark ticker (e.g. Commodities -> `^GSPC`). |

### 2. News Feeds

| Name | Type | Value | Description |
|---|---|---|---|
| `NEWS_FEEDS` | `list[tuple[str, str]]` | 12 entries | List of `(feed_name, url)` tuples. Feed name is used as the key in `SOURCE_WEIGHTS`. |

### 3. Keyword and Event Configuration

| Name | Type | Shape | Description |
|---|---|---|---|
| `ASSET_KEYWORDS` | `dict[str, list[tuple[str, int]]]` | 24 assets | Maps each asset name to a list of `(keyword, weight)` tuples. Weight is 1, 2, or 3. Used in `correlate_news`. |
| `EVENT_TRIGGERS` | `dict[str, dict]` | 8 event types | Maps event category ID to a dict with `keywords: list[str]`, `label: str`, and `icon: str`. Used in `detect_events`. |

### 4. Data Settings

| Name | Type | Default | Description |
|---|---|---|---|
| `LOOKBACK_DAYS` | `int` | 30 | Number of calendar days of price history to fetch from Yahoo Finance. |
| `PRICE_CHANGE_THRESHOLD` | `float` | 2.0 | Percent change above which the dashboard displays a significant move alert. |
| `NEWS_MAX_AGE_HOURS` | `int` | 96 | Articles older than this are discarded during ingestion. |
| `NEWS_MAX_ARTICLES` | `int` | 300 | Maximum number of articles retained in the pool after deduplication. |
| `RELEVANCE_HIGH` | `int` | 6 | Minimum relevance score for a news article to be considered high-relevance. |
| `RELEVANCE_MEDIUM` | `int` | 3 | Minimum relevance score for medium-relevance articles included in correlation. |
| `DEDUP_SIMILARITY_THRESHOLD` | `float` | 0.65 | Jaccard similarity threshold above which two articles are considered duplicates. |
| `MIN_NEWS_ARTICLES_FOR_CONFIDENCE` | `int` | 3 | Minimum number of correlated articles required for a high-confidence sentiment signal. Below this count the sentiment weight is reduced by `LOW_NEWS_SENTIMENT_WEIGHT_MULTIPLIER`. |
| `LOW_NEWS_SENTIMENT_WEIGHT_MULTIPLIER` | `float` | 0.3 | Multiplier applied to the sentiment component of the signal score when the article count is below `MIN_NEWS_ARTICLES_FOR_CONFIDENCE`. |

### 5. Dashboard Settings

| Name | Type | Default | Description |
|---|---|---|---|
| `DASHBOARD_TITLE` | `str` | `"PulseEngine"` | Browser tab title and sidebar header. |
| `DASHBOARD_ICON` | `str` | str — Absolute path to `assets/icons/favicon.ico` relative to the project root. Passed to `st.set_page_config` as the page icon. |
| `DASHBOARD_LAYOUT` | `str` | `"wide"` | Streamlit page layout. |
| `CHART_HEIGHT` | `int` | 420 | Height in pixels for Plotly price charts. |
| `DEFAULT_CATEGORY` | `str` | `"Commodities"` | Category selected on first load. |

### 6. Cache and Performance

| Name | Type | Default | Description |
|---|---|---|---|
| `PRICE_CACHE_TTL` | `int` | 90 | TTL in seconds for `@st.cache_data` on price history and metrics functions. |
| `NEWS_CACHE_TTL` | `int` | 300 | TTL in seconds for `@st.cache_data` on news fetching. |
| `REQUEST_TIMEOUT` | `int` | 20 | HTTP timeout in seconds applied to all RSS feed fetch requests. |
| `MAX_RETRIES` | `int` | 3 | Number of retry attempts for failed Yahoo Finance requests. |
| `MAX_WORKERS` | `int` | 4 | Thread pool size for parallel news fetching. |
| `PRICE_FETCH_WORKERS` | `int` | 3 | Thread pool size specifically for parallel Yahoo Finance price fetches and `run_full_scan`. |
| `YFINANCE_REQUEST_DELAY` | `float` | 0.75 | Base delay in seconds between Yahoo Finance requests to avoid rate limiting. |
| `YFINANCE_BACKOFF_BASE` | `float` | 1.0 | Multiplier base for exponential backoff on retried Yahoo Finance requests. |
### 7. Source Credibility Weights

| Name | Type | Shape | Description |
|---|---|---|---|
| `SOURCE_WEIGHTS` | `dict[str, float]` | 12 entries | Maps feed name to a credibility multiplier applied during news correlation. Range: 0.90 – 1.35. |

### 8. Momentum Settings

| Name | Type | Default | Description |
|---|---|---|---|
| `RSI_PERIOD` | `int` | 14 | Lookback window for the Relative Strength Index calculation. |
| `MOMENTUM_PERIOD` | `int` | 10 | Number of days for the rate-of-change (ROC) calculation. |

### 9. Signal Thresholds

| Name | Type | Shape | Description |
|---|---|---|---|
| `SIGNAL_THRESHOLDS` | `dict[str, float]` | 6 keys | Maps signal label identifiers to the minimum score for that label. Labels below the `bearish` threshold are classified as `strong_bearish`. |

### 10. Asset Class Weights

| Name | Type | Shape | Description |
|---|---|---|---|
| `ASSET_CLASS_WEIGHTS` | `dict[str, dict[str, float]]` | 4 classes, 6 components each | Per-class multipliers for trend, momentum, rsi, sentiment, trend_strength, and context components of the signal score. |

### 11. Storage Retention

| Name | Type | Default | Description |
|---|---|---|---|
| `STORAGE_DIR` | `str` | `"market_data"` | Relative path to the snapshot storage directory. |
| `STORAGE_FULL_DETAIL_DAYS` | `int` | 7 | Snapshots younger than this retain all fields including headlines. |
| `STORAGE_REDUCED_DETAIL_DAYS` | `int` | 30 | Snapshots between this and `STORAGE_FULL_DETAIL_DAYS` retain reduced fields. |
| `STORAGE_MAX_DAYS` | `int` | 60 | Snapshots older than this are deleted by `cleanup_old_snapshots`. |
| `SNAPSHOT_LOAD_LIMIT` | `int` | 20 | Default maximum number of snapshots loaded by `load_recent_snapshots`. |
| `BACKTEST_WINDOW` | `int` | 20 | Maximum number of historical signals evaluated in one backtest run. |
| `SCAN_INTERVAL_MINUTES` | `int` | 30 | Minimum minutes between automatic background scans. |

---

## pulseengine/core/app.py — Orchestration Module

`app/analysis.py` is a backward-compat re-export shim. All domain logic now lives in `pulseengine/core/`. Module-level variables listed below are defined in the `pulseengine/core/` sub-modules and re-exported by `pulseengine/core/__init__.py`. `VADER_AVAILABLE` and `STORAGE_AVAILABLE` are re-exported from `pulseengine/core/sentiment.py` and `pulseengine/core/app.py` respectively.

### Module-Level

| Name | Type | Description |
|---|---|---|
| `VADER_AVAILABLE` | `bool` | Set to `True` if `vaderSentiment` imported successfully, `False` if fallback keyword scoring is used. |
| `STORAGE_AVAILABLE` | `bool` | Set to `True` if `storage.save_snapshot` imported successfully. |
| `_save_snapshot` | `Callable` | Alias for `storage.save_snapshot`, or a no-op if storage is unavailable. |
| `_vader` | `SentimentIntensityAnalyzer \| None` | VADER analyzer instance. `None` if `vaderSentiment` is not installed. |
| `_yf_semaphore` | `threading.Semaphore` | Semaphore with `PRICE_FETCH_WORKERS` permits to limit concurrent Yahoo Finance requests. |
| `_FINANCE_LEXICON` | `dict[str, float]` | Custom financial sentiment words with signed weights, injected into VADER. 55+ entries. |
| `_POS_WORDS` | `frozenset[str]` | 17 positive financial terms used by the keyword fallback sentiment scorer. |
| `_NEG_WORDS` | `frozenset[str]` | 25 negative financial terms used by the keyword fallback sentiment scorer. |
| `log` | `logging.Logger` | Module-level logger named after `__name__`. |

### Function Signatures and Return Structures

#### `fetch_price_history(ticker, days)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `ticker` | `str` | — | Yahoo Finance ticker symbol |
| `days` | `int` | `LOOKBACK_DAYS` | Number of calendar days to fetch |

Returns `pd.DataFrame` with columns `Open High Low Close Volume Adj Close` indexed by date, or `None` on failure.

---

#### `compute_price_metrics(df)`

| Parameter | Type | Description |
|---|---|---|
| `df` | `Optional[pd.DataFrame]` | OHLCV DataFrame from `fetch_price_history` |

Returns `dict`:

| Key | Type | Description |
|---|---|---|
| `latest_price` | `float` | Most recent Close value |
| `change_1d` | `Optional[float]` | Percentage change over 1 trading day |
| `change_7d` | `Optional[float]` | Percentage change over 7 trading days |
| `change_30d` | `Optional[float]` | Percentage change over 30 trading days |
| `high_30d` | `float` | 30-day rolling high |
| `low_30d` | `float` | 30-day rolling low |
| `volatility` | `float` | Standard deviation of daily returns (pct_change fill_method=None) multiplied by 100 |
| `trend` | `str` | `"uptrend"`, `"downtrend"`, or `"sideways"` |

---

#### `compute_momentum_metrics(df)`

Returns `dict`:

| Key | Type | Description |
|---|---|---|
| `rsi` | `Optional[float]` | 14-period RSI. None if insufficient history |
| `roc_10d` | `Optional[float]` | 10-day rate of change as percentage |
| `trend_strength` | `Optional[float]` | Divergence of 7-day MA from 30-day MA as percentage |
| `momentum_accel` | `Optional[float]` | Recent 5-day ROC minus prior 5-day ROC |

---

#### `fetch_news_articles()`

Takes no parameters. Returns `list[dict]` where each dict contains:

| Key | Type | Description |
|---|---|---|
| `title` | `str` | Article headline, HTML stripped |
| `summary` | `str` | Article body excerpt, HTML stripped, max 600 chars |
| `source` | `str` | Feed name matching a key in `SOURCE_WEIGHTS` |
| `published` | `Optional[datetime]` | Publication datetime (UTC) |
| `sentiment` | `dict` | Output of `score_sentiment` |
| `link` | `str` | Article URL |

---

#### `score_sentiment(text)`

Returns `dict`:

| Key | Type | Description |
|---|---|---|
| `compound` | `float` | Composite score -1.0 to +1.0 |
| `pos` | `float` | Positive component 0.0 to 1.0 |
| `neg` | `float` | Negative component 0.0 to 1.0 |
| `neu` | `float` | Neutral component 0.0 to 1.0 |

---

#### `correlate_news(asset_name, articles)`

Keyword matching uses word-boundary regex (`_kw_re`) rather than plain substring containment. This prevents short keywords (e.g. `"gold"`) from matching unrelated text where they appear as a prefix or suffix of a longer word (e.g. `"goldman"`).

Returns `list[dict]` — same structure as `fetch_news_articles` output, filtered and extended with:

| Key | Type | Description |
|---|---|---|
| `relevance_score` | `float` | Final weighted score after source credibility multiplier |
| `base_score` | `float` | Raw keyword match score before source weighting |
| `source_weight` | `float` | Source credibility multiplier applied from `SOURCE_WEIGHTS` |
| `events_detected` | `list[dict]` | Event dicts from `detect_events`, each with `event_key`, `label`, `icon`, `matched_kw` |

Sorted descending by `relevance_score`.

---

#### `detect_events(text)`

| Parameter | Type | Description |
|---|---|---|
| `text` | `str` | Combined title + summary text, lowercased |

Returns `list[dict]` where each dict contains:

| Key | Type | Description |
|---|---|---|
| `event_key` | `str` | Event category identifier from `EVENT_TRIGGERS` |
| `label` | `str` | Human-readable event label |
| `icon` | `str` | Display icon for the event |
| `matched_kw` | `list[str]` | Keywords that triggered this event detection |

---

#### `cluster_articles(articles)`

| Parameter | Type | Description |
|---|---|---|
| `articles` | `list[dict]` | Correlated article list (output of `correlate_news`) |

Returns `dict[str, list[dict]]` — articles grouped by detected event type. Ungrouped articles appear under a `"general"` key.

---

#### `get_display_clusters(news, max_clusters, min_relevance)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `news` | `list[dict]` | — | Correlated article list |
| `max_clusters` | `int` | `2` | Maximum number of clusters to return |
| `min_relevance` | `Optional[float]` | `None` | Minimum relevance threshold filter |

Returns `dict` — top clusters from `cluster_articles` limited to `max_clusters` entries.

---

#### `compute_signal_score(metrics, momentum, news, market_ctx, category)`

Returns `dict`:

| Key | Type | Description |
|---|---|---|
| `score` | `float` | Composite score clamped to -10.0 to +10.0 |
| `label` | `str` | Human-readable label from `SIGNAL_THRESHOLDS` |
| `components` | `dict[str, float]` | Per-component contributions after class-weight multiplication |
| `raw_components` | `dict[str, float]` | Per-component raw values before weight multiplication |
| `category` | `Optional[str]` | Asset category passed through for downstream reference |

---

#### `analyse_market_context(asset_name, category, asset_change)`

Returns `dict`:

| Key | Type | Description |
|---|---|---|
| `peer_moves` | `dict[str, Optional[float]]` | 1-day percentage change for each sector peer |
| `benchmark_change` | `Optional[float]` | 1-day percentage change of the category benchmark |
| `is_sector_wide` | `bool` | True if >= 60% of peers moved in the same direction |
| `is_market_wide` | `bool` | True if benchmark moved > 0.5% in the same direction |
| `is_asset_specific` | `bool` | True if neither sector-wide nor market-wide |

---

#### `build_explanation(asset_name, metrics, related_news, market_ctx, momentum, signal)`

Returns `dict`:

| Key | Type | Description |
|---|---|---|
| `verdict` | `str` | One-line summary sentence |
| `why_it_matters` | `str` | Contextual significance paragraph |
| `detail` | `str` | Full markdown narrative with all contributing factors |
| `confidence` | `str` | `"high"`, `"medium"`, or `"low"` |
| `confidence_info` | `dict` | Output of `_assess_confidence` with `level`, `score`, `reasons`, `increases`, `decreases` |
| `factors` | `list[dict]` | List of factor dicts each with `type`, `label`, `detail` keys |
| `contradictions` | `list[dict]` | List of contradiction dicts each with `type` and `description` keys |

---

#### `analyse_asset(asset_name, ticker, category, articles, with_market_ctx, save, price_cache)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `asset_name` | `str` | — | Asset display name |
| `ticker` | `str` | — | Yahoo Finance ticker |
| `category` | `str` | — | Asset category |
| `articles` | `list[dict]` | — | Pre-fetched article pool |
| `with_market_ctx` | `bool` | `False` | Whether to run `analyse_market_context` |
| `save` | `bool` | `False` | Whether to persist a snapshot via `save_snapshot`. Only the batch scan pipeline passes `True`. |
| `price_cache` | `Optional[dict[str, float]]` | `None` | Pre-built `{ticker: change_1d}` map. Passed to `analyse_market_context` so peer/benchmark lookups are served from memory instead of making extra yfinance calls. Has no effect when `with_market_ctx=False`. |

Returns `dict`:

| Key | Type | Description |
|---|---|---|
| `ticker` | `str` | Yahoo Finance ticker |
| `history` | `pd.DataFrame` | Raw OHLCV DataFrame |
| `metrics` | `dict` | Output of `compute_price_metrics` |
| `momentum` | `dict` | Output of `compute_momentum_metrics` |
| `news` | `list[dict]` | Output of `correlate_news` |
| `clusters` | `dict` | Output of `cluster_articles` |
| `market_ctx` | `Optional[dict]` | Output of `analyse_market_context` or None |
| `signal` | `dict` | Output of `compute_signal_score` |
| `explanation` | `dict` | Output of `build_explanation` |
| `historical_features` | `dict` | Output of `storage.get_historical_features` |
| `error` | `Optional[dict]` | Error payload dict if price fetch failed, otherwise `None`. Contains `type`, `exception`, `stage`, `message` keys. |

---

#### `fetch_all_metrics_parallel(days)`

| Parameter | Type | Default | Description |
|---|---|---|---|
| `days` | `int` | `LOOKBACK_DAYS` | Calendar days of price history to fetch |

Fetches price metrics and momentum for every tracked asset in parallel using `PRICE_FETCH_WORKERS` threads. Returns `dict`:

```
{category: {asset_name: {"metrics": <price_metrics_dict>, "momentum": <momentum_dict>}}}
```

Called by `pulseengine/local/scan.py` during the batch pipeline to pre-build the `price_cache` before the per-asset loop (eliminating ~50–80 redundant yfinance calls). Also available for external use. The dashboard heatmap and category overview use `cached_scan_summary()` in `pulseengine/local/data.py` rather than calling this directly.

---

#### `run_full_scan()`

Takes no parameters. Fetches news once, then analyses every tracked asset in parallel using `PRICE_FETCH_WORKERS` threads with `with_market_ctx=True`. Does **not** persist snapshots (passes `save=False`). Returns:

```
{category: {asset_name: <analyse_asset_result_dict>}}
```

---

## pulseengine/core/signals.py — Module-Level Constants

| Name | Type | Description |
|---|---|---|
| `_KW_PATTERN_CACHE` | `dict[str, re.Pattern]` | Module-level cache of compiled keyword regex patterns, keyed by keyword string. Patterns are built once on first use and reused across all `correlate_news` calls. |
| `log` | `logging.Logger` | Module-level logger named after `__name__`. |

#### `_kw_re(kw)`

| Parameter | Type | Description |
|---|---|---|
| `kw` | `str` | Lowercase keyword string from `ASSET_KEYWORDS` or the auto-appended asset name |

Returns a `re.Pattern` that matches `kw` as a whole token. A leading `\b` is added only when `kw` starts with an alphanumeric character; a trailing `\b` is added only when `kw` ends with an alphanumeric character. Both guards are independent, so a keyword like `opec+` (alphanumeric start, special-char end) produces `\bopec\+` with no trailing boundary. Results are cached in `_KW_PATTERN_CACHE`.

---

## pulseengine/core/news.py — Module-Level Constants and `generate_keywords`

| Name | Type | Description |
|---|---|---|
| `_CORP_SUFFIXES` | `frozenset[str]` | Common corporate suffix words stripped from company name tokens during keyword generation (e.g. `"inc"`, `"corp"`, `"holdings"`, `"technology"`). 18 entries. |
| `log` | `logging.Logger` | Module-level logger named after `__name__`. |

#### `generate_keywords(ticker)`

| Parameter | Type | Description |
|---|---|---|
| `ticker` | `str` | Any valid Yahoo Finance ticker symbol (e.g. `"NVDA"`, `"AAPL"`) |

Fetches company metadata from `yf.Ticker(ticker).info` in a daemon thread bounded by `REQUEST_TIMEOUT`. Falls back to `[ticker]` on timeout, network failure, or unknown ticker (empty `info` dict).

Returns `list[str]` — a deduplicated list of keyword strings, all >= 3 characters, in the following order of precedence:

| Source | Example output |
|---|---|
| Ticker symbol | `"NVDA"` |
| `longName` full string | `"NVIDIA Corporation"` |
| `longName` tokens (corporate suffixes stripped) | `"NVIDIA"` |
| `shortName` tokens | `"NVIDIA"` (deduplicated away) |
| Executive surnames from `companyOfficers` (top 5) | `"Huang"`, `"Kress"` |

Industry and sector fields are intentionally excluded — terms like `"Technology"` are too broad and would cause false-positive matches across unrelated assets.

---

## pulseengine/local/dashboard.py — Session State, Singleton State, and UI Variables

### Module-Level Constants

| Name | Type | Description |
|---|---|---|
| `_NAV_DETECT_KEYS` | `tuple[str, ...]` | Session-state keys whose changes trigger a history push: `_selected_category`, `_selected_asset`, `_confirmed_custom_ticker`. |
| `_NAV_SNAPSHOT_KEYS` | `tuple[str, ...]` | Keys saved in each history snapshot (superset of `_NAV_DETECT_KEYS`; also includes `_news_for`, `_live_for`, `_custom_ticker_input`). |
| `_EGG_LIMIT` | `int` | Click count threshold for the easter egg (5). |
| `_EGG_WINDOW` | `float` | Time window in seconds for easter egg click detection (2.0 s). |
| `_EGG_URL` | `str` | URL opened when the easter egg triggers. |

### Module-Level Constants (`pulseengine/local/components.py`)

| Name | Type | Description |
|---|---|---|
| `_BACKTEST_AVAILABLE` | `bool` | `True` if `pulseengine.core.backtest` imported successfully. Controls whether the backtest section renders. |
| `_STORAGE_AVAILABLE` | `bool` | `True` if `pulseengine.core.storage.get_historical_features` imported successfully. Controls whether the historical context section renders. |

### Singleton Scan State (via `@st.cache_resource`)

| Key in `_get_scan_state()` | Type | Description |
|---|---|---|
| `lock` | `threading.Lock` | Prevents concurrent scan threads. Acquired before starting, released in `finally` block. |
| `running` | `bool` | True while a scan thread is active. |
| `last_started` | `float` | `time.time()` value when the most recent scan was initiated. |
| `last_finished` | `float` | `time.time()` value when the most recent scan completed. |
| `error` | `str` | Error message string if the last scan raised an exception, empty string otherwise. |
| `assets_done` | `int` | Number of assets successfully processed in the last scan. |
| `errors_count` | `int` | Number of per-asset errors recorded during the last scan. |

### `st.session_state` Keys

| Key | Type | Description |
|---|---|---|
| `_scan_check_ts` | `float` | `time.time()` of the last call that passed the 60-second rate-limit guard in `_maybe_trigger_scan`. |
| `_scan_refresh_epoch` | `int` | Monotonically increasing counter; incrementing it busts `cached_scan_summary()`. |
| `_scan_rerun_done` | `bool` | Guards the one-time rerun triggered when a background scan finishes. |
| `_enable_auto_scan` | `bool` | Sidebar checkbox controlling whether `_maybe_trigger_scan` is called each rerun. |
| `_confirmed_custom_ticker` | `str` | Validated Yahoo Finance ticker entered by the user, or empty string. |
| `_ticker_invalid` | `str` | Ticker symbol that failed validation; drives the "No data found" error banner. |
| `_custom_ticker_input` | `str` | Raw text from the ticker input widget. |
| `_selected_category` | `str` | Category chosen in sidebar selectbox. |
| `_selected_asset` | `str` | Asset chosen in sidebar selectbox. |
| `_news_for` | `str` | Ticker for which the news feed has been loaded; drives the deferred news section. |
| `_live_for` | `str` | Ticker for which live analysis has been loaded; drives the deferred live-analysis expander. |
| `_nav_history` | `list[dict]` | Stack of page-state snapshots. Each entry holds the `_NAV_SNAPSHOT_KEYS` values from a previous rerun. Capped at 20 entries. |
| `_last_nav_snapshot` | `dict` | Snapshot of the current page's `_NAV_SNAPSHOT_KEYS` values, saved at the end of `_push_nav_if_changed()` for comparison on the next rerun. |
| `_nav_restoring` | `bool` | Set to `True` by `_restore_nav_state()`. Tells `_push_nav_if_changed()` on the immediately following rerun to skip the push, preventing the restore itself from generating a spurious history entry. |
| `_egg_clicks` | `list[float]` | Timestamps of recent easter egg button clicks within the detection window. |

### Cached Data Functions (`pulseengine/local/data.py`)

| Function | TTL | Returns |
|---|---|---|
| `cached_news()` | `NEWS_CACHE_TTL` (300 s) | Deduplicated article list from all 12 feeds |
| `cached_scan_summary(epoch)` | `PRICE_CACHE_TTL` (90 s) | Nested summary dict loaded from `_scan_summary.json.gz`; used to populate the market heatmap and category overview |
| `cached_live_analysis(...)` | `PRICE_CACHE_TTL` (90 s) | Full `analyse_asset` result dict for the selected ticker |
| `cached_generated_keywords(ticker)` | `PRICE_CACHE_TTL` (90 s) | Keyword list from `generate_keywords` for a custom ticker |

### UI Rendering Functions (`pulseengine/local/components.py`)

| Function | Description |
|---|---|
| `sidebar_header_html()` | Returns HTML for the sidebar logo and title header |
| `render_scan_status_sidebar(scan_state, summary)` | Renders the scan status badge and last-scan timestamp in the sidebar |
| `render_signal_legend_sidebar()` | Renders the signal score legend in the sidebar |
| `render_mover_rows(gainers, losers, summary_date)` | Renders the top movers (gainers and losers) in the sidebar |
| `render_data_status_banner(scan_state, stale, summary)` | Renders a banner when a scan is running or data is stale |
| `render_signal_card(snap, category, asset, chg_1d, is_significant)` | Renders the main signal card with score, label, and alert badge |
| `render_why_box(snap)` | Renders the "why it matters" narrative box |
| `render_snapshot_metrics(snap, chg_1d)` | Renders the snapshot-data metric cards |
| `render_article(item)` | Renders a single correlated news article card |
| `render_news_section(clusters, suppressed_count, total, news)` | Renders the full news section with clusters and article cards |
| `render_live_analysis(history, asset, signal, explanation, snap, is_significant)` | Renders the price chart, live signal, explanation, backtest, and historical context |
| `render_heatmap(summary, summary_date)` | Renders the market heatmap Plotly chart |
| `render_category_overview(cat_data, summary_date)` | Renders the category overview table |

### Per-Rerun Variables (main panel)

| Variable | Type | Description |
|---|---|---|
| `selected_category` | `str` | Category chosen in sidebar selectbox (or `"Custom Ticker"` when using a custom ticker) |
| `selected_asset` | `str` | Asset chosen in sidebar selectbox (or the confirmed custom ticker symbol) |
| `ticker` | `str` | Yahoo Finance ticker for `selected_asset` |
| `using_custom_ticker` | `bool` | True when `_confirmed_custom_ticker` is set and non-empty |
| `snap` | `dict` | Latest snapshot entry from `_summary_results` for the selected asset |
| `chg_1d` | `Optional[float]` | 1-day price change extracted from `snap` |
| `is_significant` | `bool` | True if `abs(chg_1d) >= PRICE_CHANGE_THRESHOLD` |

---

## pulseengine/core/storage.py — Internal Variables and Return Structures

### Module-Level

| Name | Type | Description |
|---|---|---|
| `_storage_path` | `pathlib.Path` | Resolved path to `STORAGE_DIR`. |
| `_asset_locks` | `dict[str, threading.Lock]` | Per-asset write locks to prevent concurrent snapshot writes for the same asset. |
| `_asset_locks_mutex` | `threading.Lock` | Guards access to `_asset_locks` dict during lock creation. |
| `_REDUCED_FIELDS` | `frozenset[str]` | Field names retained in reduced-detail snapshots. |
| `_PRICE_WRITE_THRESHOLD` | `float` | Minimum absolute price change (0.01) required to rewrite an existing snapshot for the same day. |
| `_SCORE_WRITE_THRESHOLD` | `float` | Minimum absolute signal score change (0.5) required to rewrite an existing snapshot for the same day. |
| `log` | `logging.Logger` | Module logger. |

### Snapshot Dict Structure (full detail)

| Key | Type | Description |
|---|---|---|
| `asset` | `str` | Asset name |
| `date` | `str` | ISO date string `YYYY-MM-DD` |
| `price` | `Optional[float]` | Latest close price |
| `change_1d` | `Optional[float]` | 1-day percentage change |
| `change_7d` | `Optional[float]` | 7-day percentage change |
| `change_30d` | `Optional[float]` | 30-day percentage change |
| `volatility` | `Optional[float]` | Daily return std deviation * 100 |
| `trend` | `Optional[str]` | Trend classification string |
| `rsi` | `Optional[float]` | 14-period RSI |
| `roc_10d` | `Optional[float]` | 10-day rate of change |
| `trend_strength` | `Optional[float]` | MA divergence percentage |
| `momentum_accel` | `Optional[float]` | ROC acceleration |
| `signal_score` | `Optional[float]` | Composite signal score |
| `signal_label` | `Optional[str]` | Signal label string |
| `headlines` | `list[dict]` | Top 5 headlines each with `title`, `source`, `sentiment` (float) |

### Reduced-Detail Fields (`_REDUCED_FIELDS`)

`asset`, `date`, `price`, `change_1d`, `signal_score`, `signal_label`, `trend`, `rsi`, `roc_10d`, `trend_strength`

### Additional Functions

| Function | Description |
|---|---|
| `load_snapshots(asset_name, days=30)` | Returns `list[dict]` of all snapshots for the asset within the last `days` calendar days |
| `list_tracked_assets_with_history()` | Returns sorted `list[str]` of asset names that have at least one stored snapshot |

### `get_historical_features(asset_name)` Return Structure

| Key | Type | Description |
|---|---|---|
| `available` | `int` | Number of snapshots found |
| `signal_consistency` | `Optional[float]` | Fraction of historical signals in same direction as latest |
| `trend_persistence` | `int` | Consecutive days the current trend has held |
| `today_vs_yesterday` | `dict` | Field-level comparison of latest vs previous snapshot |

---

## pulseengine/local/scan.py — Return Structures

### Module-Level

| Name | Type | Description |
|---|---|---|
| `_SUMMARY_FILE` | `pathlib.Path` | Path to `market_data/_scan_summary.json.gz` — the persistent scan summary written after each run. |
| `log` | `logging.Logger` | Module logger. |

### `run_scan(verbose, dry_run)` Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `verbose` | `bool` | `True` | Log per-asset progress lines |
| `dry_run` | `bool` | `False` | Run the full pipeline but skip all file writes |

### `run_scan()` Return Structure

| Key | Type | Description |
|---|---|---|
| `scan_date` | `str` | ISO date string of scan execution |
| `scan_time` | `str` | ISO datetime string of scan start |
| `total` | `int` | Total number of assets processed |
| `succeeded` | `int` | Number of assets that completed without error |
| `errors` | `list[dict]` | List of error dicts each with `asset`, `category`, `type`, `stage`, `message` keys |
| `results` | `dict[str, dict[str, dict]]` | Nested `{category: {asset_name: entry_dict}}` |
| `top_movers` | `dict` | Pre-computed dict with `gainers` and `losers` lists (top 5 each by 24h change) |
| `heatmap` | `dict` | Pre-computed heatmap matrix with `z`, `text`, `categories`, `max_assets` keys for the Plotly heatmap |
| `category_rows` | `dict` | Pre-computed per-category row data: `{category: {"rows": list, "missing": list}}` |

### Entry Dict Within `results`

| Key | Type | Description |
|---|---|---|
| `ticker` | `str` | Yahoo Finance ticker |
| `signal_score` | `Optional[float]` | Composite score |
| `signal_label` | `Optional[str]` | Label string |
| `price` | `Optional[float]` | Latest close price |
| `change_1d` | `Optional[float]` | 1-day percentage change |
| `change_7d` | `Optional[float]` | 7-day percentage change |
| `change_30d` | `Optional[float]` | 30-day percentage change |
| `volatility` | `Optional[float]` | Daily return std deviation * 100 |
| `trend` | `Optional[str]` | Trend classification |
| `rsi` | `Optional[float]` | 14-period RSI |
| `roc_10d` | `Optional[float]` | 10-day ROC |
| `trend_strength` | `Optional[float]` | MA divergence percentage |
| `momentum_accel` | `Optional[float]` | ROC acceleration |
| `confidence` | `Optional[str]` | Explanation confidence level |
| `verdict` | `str` | One-line summary string |
| `is_market_wide` | `bool` | True if the benchmark moved > 0.5% in the same direction |
| `is_sector_wide` | `bool` | True if >= 60% of sector peers moved in the same direction |
| `error` | `Optional[dict]` | Error payload if price fetch failed, otherwise absent |

### `load_last_scan_summary()` Return Structure

Returns the dict written by the most recent `run_scan()` call (same structure as `run_scan` return), or an empty dict `{}` if no summary file exists.

---

## pulseengine/core/backtest.py — Return Structures

### Module-Level

| Name | Type | Description |
|---|---|---|
| `_STRONG_THRESHOLD` | `float` | 6.0 — minimum `abs(signal_score)` for the `strong` bucket. |
| `_MODERATE_THRESHOLD` | `float` | 3.0 — minimum `abs(signal_score)` for the `moderate` bucket. Scores below this are `weak`. |
| `log` | `logging.Logger` | Module logger. |

### `evaluate_signal_accuracy(asset_name, lookback)` Return Structure

| Key | Type | Description |
|---|---|---|
| `hit_rate` | `Optional[float]` | Fraction of correct directional predictions. None if fewer than 2 pairs available |
| `num_evaluated` | `int` | Number of signal-outcome pairs evaluated |
| `details` | `list[dict]` | Per-pair records sorted newest-first. Each dict has `date`, `signal_score`, `signal_label`, `predicted`, `actual_change`, `actual`, `correct` |
| `avg_signal_score` | `Optional[float]` | Mean absolute signal score across evaluated pairs |
| `message` | `str` | Human-readable result summary string |
| `by_signal_strength` | `dict` | Hit rate and count broken down by `strong`, `moderate`, `weak` buckets |
| `by_label` | `dict` | Hit rate and count per signal label |
| `label_summaries` | `list[str]` | Human-readable text summaries per label |

### `evaluate_all_assets(lookback)` Return Structure

Returns `dict[str, dict]` — one `evaluate_signal_accuracy` result per asset name, each extended with a `category` key.

### `get_signal_streak(details)` Return Structure

| Key | Type | Description |
|---|---|---|
| `type` | `str` | `"win"`, `"loss"`, or `"none"` |
| `length` | `int` | Number of consecutive matching outcomes |

---

## install.py — Installer Constants and Functions

### Constants

| Name | Type | Value | Description |
|---|---|---|---|
| `MIN_PYTHON` | `tuple[int, int]` | `(3, 11)` | Minimum supported Python version (inclusive). |
| `MAX_PYTHON` | `tuple[int, int]` | `(3, 14)` | Maximum tested Python version (inclusive). |
| `REPO_ROOT` | `pathlib.Path` | `Path(__file__).resolve().parent` | Absolute path to the project root, resolved from the installer's own location. |
| `VENV_DIR` | `pathlib.Path` | `REPO_ROOT / ".venv"` | Path to the virtual environment directory created by the installer. |
| `REQUIREMENTS` | `pathlib.Path` | `REPO_ROOT / "requirements.txt"` | Path to the pinned dependency file passed to `pip install -r`. |
| `VERIFY_IMPORTS` | `list[str]` | `["streamlit", "yfinance", "pandas", "plotly", "feedparser", "vaderSentiment"]` | Package names imported inside the venv to confirm installation succeeded. |
| `_USE_COLOUR` | `bool` | `True` on Unix TTYs, `False` on Windows and non-TTY stdout | Controls whether ANSI escape codes are emitted by the colour helper functions. |

### Helper Functions

| Function | Signature | Description |
|---|---|---|
| `_c(code, text)` | `(str, str) -> str` | Wraps `text` in the ANSI escape sequence for `code` if `_USE_COLOUR` is set, otherwise returns `text` unchanged. |
| `green(t)` | `(str) -> str` | Green-coloured text. Used for success checkmarks. |
| `yellow(t)` | `(str) -> str` | Yellow-coloured text. Used for warnings. |
| `red(t)` | `(str) -> str` | Red-coloured text. Used for error messages. |
| `bold(t)` | `(str) -> str` | Bold text. Used for step numbers and emphasis. |
| `cyan(t)` | `(str) -> str` | Cyan-coloured text. Used for banner borders and labels. |
| `_banner()` | `() -> None` | Prints the installer banner to stdout. |
| `_step(n, total, msg)` | `(int, int, str) -> None` | Prints a numbered step line, e.g. `[2/5] Creating virtual environment`. |
| `_ok(msg)` | `(str) -> None` | Prints a green checkmark success line. |
| `_warn(msg)` | `(str) -> None` | Prints a yellow warning line (non-fatal). |
| `_fail(msg)` | `(str) -> None` | Prints a red error line. |
| `_abort(msg, hint)` | `(str, str) -> None` | Prints the error and optional hint, then calls `sys.exit(1)`. |

### Path Helpers

| Function | Signature | Returns | Description |
|---|---|---|---|
| `_venv_python()` | `() -> pathlib.Path` | `.venv/Scripts/python.exe` (Windows) or `.venv/bin/python` (Unix) | Path to the Python executable inside the virtual environment. |
| `_venv_pip()` | `() -> pathlib.Path` | `.venv/Scripts/pip.exe` (Windows) or `.venv/bin/pip` (Unix) | Path to the pip executable inside the virtual environment. |

### Pipeline Functions

| Function | Description |
|---|---|
| `check_python_version()` | Reads `sys.version_info` and calls `_abort` if the version is outside `MIN_PYTHON`–`MAX_PYTHON`. |
| `create_venv()` | Runs `python -m venv .venv` via subprocess. Skips silently if `.venv/` already exists. Aborts with the subprocess stderr on failure. |
| `install_dependencies()` | First upgrades pip silently, then runs `pip install -r requirements.txt` with output streamed to the terminal. Aborts on non-zero exit code. |
| `verify_install()` | Runs `python -c "import <pkg>"` for each entry in `VERIFY_IMPORTS` using `_venv_python()`. Warns per-package on failure and aborts at the end if any import failed. |
| `generate_launch_script()` | Writes the platform-appropriate launch script(s) and returns the primary `pathlib.Path`. On Windows writes both `launch.bat` and `launch.ps1`. On Unix writes `launch.sh` and sets `chmod 0o755`. |
| `print_success(launch_path)` | Prints the post-install next-steps message showing platform-specific launch options and the dashboard URL. |
| `main()` | Orchestrates all five steps in order: `check_python_version` → `create_venv` → `install_dependencies` → `verify_install` → `generate_launch_script`, then calls `print_success`. |
