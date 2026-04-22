# Code Flow Reference

[![Module: pulseengine/core/app.py](https://img.shields.io/badge/Module-pulseengine/core/app.py-3776AB?style=flat-square)]()
[![Module: pulseengine/local/dashboard.py](https://img.shields.io/badge/Module-pulseengine/local/dashboard.py-FF4B4B?style=flat-square)]()
[![Module: pulseengine/local/scan.py](https://img.shields.io/badge/Module-pulseengine/local/scan.py-22c55e?style=flat-square)]()
[![Module: pulseengine/core/storage.py](https://img.shields.io/badge/Module-pulseengine/core/storage.py-f59e0b?style=flat-square)]()
[![Module: pulseengine/core/backtest.py](https://img.shields.io/badge/Module-pulseengine/core/backtest.py-7c3aed?style=flat-square)]()
[![Module: pulseengine/core/config.py](https://img.shields.io/badge/Module-pulseengine/core/config.py-64748b?style=flat-square)]()

This document traces the execution path of every major pipeline in the system. Each section uses a Mermaid diagram with butterfly-wing branching — decision nodes fan outward symmetrically and re-converge at a common continuation point, matching the natural branching shape of the analysis pipelines.

---

## 1. Application Startup and Dashboard Lifecycle

When `streamlit run pulseengine/local/dashboard.py` is executed, Streamlit re-runs the entire script on every rerun triggered by user interaction or the 90-second auto-refresh. The singleton scan state is created exactly once per process using `@st.cache_resource`.

```mermaid
flowchart TD
    START([streamlit run pulseengine/local/dashboard.py]) --> IMPORT[Imports resolved\npulseengine.core.config / pulseengine.core.app / pulseengine.core.backtest / pulseengine.core.storage]
    IMPORT --> SINGLETON[_get_scan_state called\nLock and status dict created once\nvia cache_resource]
    SINGLETON --> TRIGGER[_maybe_trigger_scan]

    TRIGGER --> RATECHECK{session _scan_check_ts\n< 60 s ago?}
    RATECHECK -->|Yes — skip| SIDEBAR
    RATECHECK -->|No — proceed| MTIMECHECK

    MTIMECHECK{_scan_summary.json.gz\nmtime < SCAN_INTERVAL?}
    MTIMECHECK -->|Recent enough| SIDEBAR
    MTIMECHECK -->|Missing or stale| LOCKCHECK

    LOCKCHECK{lock.acquire\nblocking=False}
    LOCKCHECK -->|Already held| SIDEBAR
    LOCKCHECK -->|Acquired| THREAD

    THREAD[Spawn daemon thread\n_run_background_scan] --> SIDEBAR

    SIDEBAR[Render sidebar\ncategory and asset selectors\nscan status badge] --> MAINPANEL
    MAINPANEL[Render main panel\nfor selected asset] --> AUTOREFRESH{90 s elapsed?}
    AUTOREFRESH -->|Yes| TRIGGER
    AUTOREFRESH -->|No| WAIT([Waiting for user or timer])
```

---

## 2. Background Full-Market Scan

`_run_background_scan` delegates entirely to `pulseengine.local.scan.run_scan()`. News is fetched once and reused across all 24 assets. A `price_cache` (`{ticker: change_1d}`) is pre-built via `fetch_all_metrics_parallel` before the loop, eliminating redundant yfinance calls during context analysis. Each asset is analysed with `with_market_ctx=True` and `save=True`.

```mermaid
flowchart TD
    ENTRY([_run_background_scan thread starts]) --> SETRUNNING[state running = True\nstate error = empty\nstate assets_done = 0]

    SETRUNNING --> RUNSCAN[scan.run_scan\nverbose=False]

    RUNSCAN --> FETCHNEWS[fetch_news_articles\nall 12 RSS feeds in parallel\ndeduplication applied]

    FETCHNEWS --> LOOPSTART{Next asset in\nTRACKED_ASSETS?}

    LOOPSTART -->|More assets| ANALYSE[analyse_asset\nasset_name ticker category articles\nwith_market_ctx=True\nsave=True\nprice_cache=price_cache]
    LOOPSTART -->|All done| SUMMARY

    ANALYSE --> ASUCCESS{Success?}
    ASUCCESS -->|Yes — extract fields| ENTRY_DICT[Build entry dict\nticker signal_score price\nchange_1d trend rsi verdict]
    ASUCCESS -->|Exception| ERRLOG[Log error\nappend to errors list]

    ENTRY_DICT --> SNAPSHOT[save_snapshot called inside\nanalyse_asset when save=True\nwrites AssetName_YYYYMMDD.json.gz]
    ERRLOG --> LOOPSTART
    SNAPSHOT --> LOOPSTART

    SUMMARY[_save_summary\nwrites _scan_summary.json.gz] --> RETENTION[apply_retention_policy\ncleanup_old_snapshots]
    RETENTION --> SCANRET[run_scan returns\nsummary dict]

    SCANRET --> DONE[state running = False\nstate assets_done = summary.succeeded\nlock released]
    DONE --> EXIT([Thread exits])
```

---

## 3. Price Data Pipeline

`fetch_price_history` retrieves raw OHLCV data. `compute_price_metrics` and `compute_momentum_metrics` derive all scalar indicators from the Close series.

```mermaid
flowchart TD
    CALL([compute_price_metrics called]) --> NULLCHECK{df is None\nor empty?}

    NULLCHECK -->|Yes| EMPTYRET([Return empty dict])
    NULLCHECK -->|No| EXTRACT[Extract Close series\nhandle DataFrame vs Series]

    EXTRACT --> LATEST[latest = close.iloc last]

    LATEST --> SAFEPCT[safe_pct helper\ncompute 1d 7d 30d changes]

    SAFEPCT --> VOLBRANCH{len close > 1?}
    VOLBRANCH -->|Yes| VOLCALC[vol = pct_change fill_method=None\n.std * 100]
    VOLBRANCH -->|No| VOLZERO[vol = 0.0]

    VOLCALC --> TREND[_classify_trend\n7-day MA vs 30-day MA]
    VOLZERO --> TREND

    TREND --> TRENDBRANCH{Enough history\nfor MAs?}
    TRENDBRANCH -->|Yes — compare MAs| TRENDLABEL[uptrend / downtrend / sideways]
    TRENDBRANCH -->|No| TRENDUNK[trend = unknown]

    TRENDLABEL --> RETDICT([Return metrics dict])
    TRENDUNK --> RETDICT
```

---

## 4. Momentum Metrics Pipeline

```mermaid
flowchart TD
    CALL([compute_momentum_metrics called]) --> NULLCHECK{df is None\nor empty?}
    NULLCHECK -->|Yes| EMPTY([Return empty dict])
    NULLCHECK -->|No| CLOSE[Extract Close series]

    CLOSE --> RSI_CHECK{len >= RSI_PERIOD + 1?}
    RSI_CHECK -->|Yes| RSI_CALC[_compute_rsi\nEWM gain loss ratio\n14-period]
    RSI_CHECK -->|No| RSI_NONE[rsi = None]

    CLOSE --> ROC_CHECK{len >= MOMENTUM_PERIOD + 1?}
    ROC_CHECK -->|Yes| ROC_CALC[_compute_roc\nclose now vs close N days ago\nas percentage]
    ROC_CHECK -->|No| ROC_NONE[roc_10d = None]

    CLOSE --> TS_CHECK{len >= 30?}
    TS_CHECK -->|Yes| TS_CALC[trend_strength\n7d MA minus 30d MA\ndivided by 30d MA * 100]
    TS_CHECK -->|No| TS_NONE[trend_strength = None]

    CLOSE --> ACCEL_CHECK{len >= 11?}
    ACCEL_CHECK -->|Yes| ACCEL_CALC[momentum_accel\nrecent 5d ROC minus prior 5d ROC]
    ACCEL_CHECK -->|No| ACCEL_NONE[momentum_accel = None]

    RSI_CALC --> MERGE
    RSI_NONE --> MERGE
    ROC_CALC --> MERGE
    ROC_NONE --> MERGE
    TS_CALC --> MERGE
    TS_NONE --> MERGE
    ACCEL_CALC --> MERGE
    ACCEL_NONE --> MERGE

    MERGE([Return momentum dict])
```

---

## 5. News Ingestion and Deduplication Pipeline

```mermaid
flowchart TD
    CALL([fetch_news_articles called]) --> PARALLEL[ThreadPoolExecutor\nMAX_WORKERS = 4\nfetch each of 12 feeds]

    PARALLEL --> PARSE[feedparser.parse each URL\nwith REQUEST_TIMEOUT = 20s]

    PARSE --> AGEFILT{article pub_date\n< NEWS_MAX_AGE_HOURS?}
    AGEFILT -->|Too old| DISCARD1[Discard]
    AGEFILT -->|Recent| SENTIMENT[score_sentiment on title + summary\nVADER with financial lexicon\nor keyword fallback]

    SENTIMENT --> POOL[Collect all articles\ninto pool]

    POOL --> CAPCHECK{len pool\n> NEWS_MAX_ARTICLES?}
    CAPCHECK -->|Over cap| TRUNCATE[Sort by relevance\ntake top 300]
    CAPCHECK -->|Under cap| DEDUP

    TRUNCATE --> DEDUP[deduplicate_articles\nJaccard similarity on title tokens\nthreshold = 0.65]
    DEDUP --> RETURN([Return deduplicated list])
```

---

## 6. Keyword Generation Pipeline

`generate_keywords` is a utility in `pulseengine/core/news.py` that auto-builds a keyword list for any ticker using Yahoo Finance metadata. It is used by the dashboard when the user enters a custom ticker, and falls back gracefully on network failure or unknown symbols.

```mermaid
flowchart TD
    CALL([generate_keywords called\nticker]) --> UPPER[Normalise ticker to uppercase]

    UPPER --> THREAD[Start daemon thread\nthread.join timeout=REQUEST_TIMEOUT]

    THREAD --> FETCH[yf.Ticker ticker .info]

    FETCH --> ALIVE{thread.is_alive\nafter join?}
    ALIVE -->|Yes — timed out| FALLBACK([Return ticker])
    ALIVE -->|No| EXCCHECK

    EXCCHECK{Exception\nraised in thread?}
    EXCCHECK -->|Yes| FALLBACK
    EXCCHECK -->|No| INFOCHECK

    INFOCHECK{info dict has\nlongName?}
    INFOCHECK -->|No — unknown ticker| FALLBACK
    INFOCHECK -->|Yes| BUILD

    BUILD[Add ticker symbol] --> NAMES[Add longName and shortName\nfull string plus individual tokens\nstrip _CORP_SUFFIXES words]

    NAMES --> OFFICERS[Add surnames from\ncompanyOfficers top 5]

    OFFICERS --> DEDUP[Deduplicate preserving order\nfilter tokens < 3 chars]

    DEDUP --> RETURN([Return keyword list])
```

---

## 7. News Correlation Pipeline

```mermaid
flowchart TD
    CALL([correlate_news called\nasset_name articles]) --> KWLOOKUP[Load ASSET_KEYWORDS\nfor this asset]

    KWLOOKUP --> ARTLOOP{Next article?}
    ARTLOOP -->|Done| SORT

    ARTLOOP -->|Process| TEXT[Combine title + summary text\nlowercase]
    TEXT --> KWSCAN[Scan each keyword via _kw_re\nword-boundary regex match\naccumulate weighted score]

    KWSCAN --> RECENCY{pub_date age?}
    RECENCY -->|< 24 h| BONUS2[Add recency bonus +2]
    RECENCY -->|< 48 h| BONUS1[Add recency bonus +1]
    RECENCY -->|Older| NOBONUS[No bonus]

    BONUS2 --> SRCWEIGHT[Multiply by SOURCE_WEIGHTS\nmultiplier for this feed]
    BONUS1 --> SRCWEIGHT
    NOBONUS --> SRCWEIGHT

    SRCWEIGHT --> THRESHOLD{relevance_score\n> 0?}
    THRESHOLD -->|Yes — include| EVENTS[detect_events\nidentify event type labels]
    THRESHOLD -->|No| ARTLOOP

    EVENTS --> ARTLOOP

    SORT[Sort by relevance_score descending] --> RETURN([Return correlated article list])
```

---

## 8. Signal Scoring Pipeline

Six components are computed from separate data sources, each multiplied by an asset-class-specific weight, then summed and clamped to the -10 to +10 range.

```mermaid
flowchart TD
    CALL([compute_signal_score called]) --> WEIGHTS[Load ASSET_CLASS_WEIGHTS\nfor this category]

    WEIGHTS --> TREND_C[Trend component\n+2.0 uptrend / -2.0 downtrend / 0 sideways\nmultiplied by class weight]
    WEIGHTS --> MOM_C[Momentum component\nROC capped at +/- 2.0\nmultiplied by class weight]
    WEIGHTS --> RSI_C[RSI component\n+/- 1.0 on overbought/oversold\nmultiplied by class weight]
    WEIGHTS --> SENT_C[Sentiment component\navg compound * 4.0 capped +/- 2.0\nmultiplied by class weight]
    WEIGHTS --> TS_C[Trend strength component\nMA divergence capped +/- 1.0\nmultiplied by class weight]
    WEIGHTS --> CTX_C[Context component\npeer and benchmark alignment +/- 1.0\nmultiplied by class weight]

    TREND_C --> SUM
    MOM_C --> SUM
    RSI_C --> SUM
    SENT_C --> SUM
    TS_C --> SUM
    CTX_C --> SUM

    SUM[Sum all components] --> CLAMP[Clamp to -10.0 / +10.0]
    CLAMP --> LABEL[Map score to label\nusing SIGNAL_THRESHOLDS]
    LABEL --> RETURN([Return score and label dict])
```

---

## 9. Market Context Analysis Pipeline

```mermaid
flowchart TD
    CALL([analyse_market_context called\nasset_name category asset_change]) --> PEERS[Load SECTOR_PEERS\nfor this asset]
    PEERS --> BENCHMARK[Load MARKET_BENCHMARK\nfor this category]

    PEERS --> PEER_FETCH[Fetch 1d change\nfor each peer in parallel]
    BENCHMARK --> BENCH_FETCH[Fetch 1d change\nfor benchmark ticker]

    PEER_FETCH --> PEER_DIR{Count peers moving\nsame direction as asset}
    PEER_DIR -->|>= 60% same direction| SECTOR_WIDE[is_sector_wide = True]
    PEER_DIR -->|< 60%| NOT_SECTOR[is_sector_wide = False]

    BENCH_FETCH --> BENCH_DIR{Benchmark moved\n> 0.5% same direction?}
    BENCH_DIR -->|Yes| MARKET_WIDE[is_market_wide = True]
    BENCH_DIR -->|No| NOT_MARKET[is_market_wide = False]

    SECTOR_WIDE --> SPECIFIC_CHECK
    NOT_SECTOR --> SPECIFIC_CHECK
    MARKET_WIDE --> SPECIFIC_CHECK
    NOT_MARKET --> SPECIFIC_CHECK

    SPECIFIC_CHECK{Neither sector\nnor market wide?}
    SPECIFIC_CHECK -->|Yes| ASSET_SPECIFIC[is_asset_specific = True]
    SPECIFIC_CHECK -->|No| NOT_SPECIFIC[is_asset_specific = False]

    ASSET_SPECIFIC --> RETURN([Return context dict])
    NOT_SPECIFIC --> RETURN
```

---

## 10. Explanation Builder Pipeline

```mermaid
flowchart TD
    CALL([build_explanation called]) --> ABNORM{Z-score of 1d change\nvs historical volatility}
    ABNORM -->|Abnormal move| ADD_VOL[Add volatility factor]
    ABNORM -->|Normal| SKIP_VOL[Skip]

    CALL --> RSI_CHK{RSI value?}
    RSI_CHK -->|> 70 overbought| ADD_OVER[Add RSI overbought factor]
    RSI_CHK -->|< 30 oversold| ADD_UNDER[Add RSI oversold factor]
    RSI_CHK -->|Normal range| SKIP_RSI[Skip]

    CALL --> CTX_CHK{Market context\navailable?}
    CTX_CHK -->|Yes| CTXFACTOR[Add sector_wide / market_wide\nor asset_specific factor]
    CTX_CHK -->|No| SKIP_CTX[Skip]

    CALL --> NEWS_CHK{High-relevance\nnews present?}
    NEWS_CHK -->|Yes| SENTFACTOR[Add sentiment factor\nwith event labels]
    NEWS_CHK -->|No| SKIP_NEWS[Skip]

    ADD_VOL --> CONTRA
    SKIP_VOL --> CONTRA
    ADD_OVER --> CONTRA
    ADD_UNDER --> CONTRA
    SKIP_RSI --> CONTRA
    CTXFACTOR --> CONTRA
    SKIP_CTX --> CONTRA
    SENTFACTOR --> CONTRA
    SKIP_NEWS --> CONTRA

    CONTRA{Signal direction\ncontradicts news sentiment?}
    CONTRA -->|Yes| ADD_CONTRA[Append contradiction to list]
    CONTRA -->|No| SKIP_CONTRA[Skip]

    ADD_CONTRA --> CONFIDENCE
    SKIP_CONTRA --> CONFIDENCE

    CONFIDENCE{Factor count\nand contradiction count}
    CONFIDENCE -->|Many factors no contra| HIGH[confidence = high]
    CONFIDENCE -->|Some factors or 1 contra| MEDIUM[confidence = medium]
    CONFIDENCE -->|Few factors or many contra| LOW[confidence = low]

    HIGH --> VERDICT[Build verdict one-liner\nbuild why_it_matters\nbuild detail markdown]
    MEDIUM --> VERDICT
    LOW --> VERDICT

    VERDICT --> RETURN([Return explanation dict])
```

---

## 11. Storage Persistence Pipeline

```mermaid
flowchart TD
    CALL([save_snapshot called\nasset_name metrics momentum signal top_headlines]) --> ENSUREDIR[_ensure_dir\ncreate market_data if absent]

    ENSUREDIR --> PATH[Build path\nmarket_data/AssetName_YYYYMMDD.json.gz]

    PATH --> HEADLINES[Trim and normalise\ntop 5 headlines\nextract compound sentiment float]

    HEADLINES --> BUILD[Assemble snapshot dict\n15 fields including price trend\nrsi signal_score headlines]

    BUILD --> WRITE[gzip compress JSON\nwrite to file\noverwrite existing for today]

    WRITE --> DONE([Return])
```

---

## 12. Retention Policy Pipeline

Run automatically at the end of each scan.

```mermaid
flowchart TD
    CALL([apply_retention_policy called]) --> LISTFILES[Glob market_data\nfor all *.json.gz excluding summary]

    LISTFILES --> FILELOOP{Next file?}
    FILELOOP -->|Done| CLEANUP[cleanup_old_snapshots\ndelete files older than STORAGE_MAX_DAYS]
    FILELOOP -->|Process| AGECHECK{File age in days}

    AGECHECK -->|<= STORAGE_FULL_DETAIL_DAYS| KEEP_FULL[Keep full snapshot unchanged]
    AGECHECK -->|<= STORAGE_REDUCED_DETAIL_DAYS| REDUCED_CHECK{Already reduced?}
    AGECHECK -->|> STORAGE_REDUCED_DETAIL_DAYS| KEEP_FULL

    REDUCED_CHECK -->|Has headlines field| REWRITE[Rewrite with only _REDUCED_FIELDS\nstrip headlines and extra fields]
    REDUCED_CHECK -->|Already reduced| KEEP_FULL

    KEEP_FULL --> FILELOOP
    REWRITE --> FILELOOP

    CLEANUP --> DONE([Return deleted count])
```

---

## 13. Backtesting Pipeline

```mermaid
flowchart TD
    CALL([evaluate_signal_accuracy called\nasset_name lookback]) --> LOAD[load_recent_snapshots\nup to lookback + 1 snapshots]

    LOAD --> ENOUGH{At least 2 snapshots?}
    ENOUGH -->|No| EMPTY([Return empty result])
    ENOUGH -->|Yes| PAIR[Pair consecutive snapshots\nday N signal vs day N+1 price change]

    PAIR --> EVAL_LOOP{Next pair?}
    EVAL_LOOP -->|Done| AGGREGATE
    EVAL_LOOP -->|Process| DIRECTION{signal_score direction\nmatch price change direction?}

    DIRECTION -->|Match| HIT[correct = True]
    DIRECTION -->|Mismatch| MISS[correct = False]

    HIT --> STRENGTH{abs score}
    MISS --> STRENGTH

    STRENGTH -->|>= 6.0| STRONG[bucket = strong]
    STRENGTH -->|>= 3.0| MODERATE[bucket = moderate]
    STRENGTH -->|< 3.0| WEAK[bucket = weak]

    STRONG --> EVAL_LOOP
    MODERATE --> EVAL_LOOP
    WEAK --> EVAL_LOOP

    AGGREGATE[Compute hit_rate\nby_signal_strength\nby_label\navg_signal_score] --> STREAK[get_signal_streak\ncurrent win or loss run]

    STREAK --> RETURN([Return result dict])
```

---

## 14. Full analyse_asset Orchestration

This is the top-level function called by both `pulseengine/local/scan.py` and directly by `pulseengine/local/dashboard.py`.

```mermaid
flowchart TD
    CALL([analyse_asset called\nasset_name ticker category articles\nwith_market_ctx]) --> PRICE[fetch_price_history ticker]

    PRICE --> PCHECK{DataFrame returned?}
    PCHECK -->|None or empty| METRICS_EMPTY[compute_price_metrics returns empty dict]
    PCHECK -->|Valid| METRICS[compute_price_metrics]

    METRICS_EMPTY --> MOMENTUM
    METRICS --> MOMENTUM[compute_momentum_metrics]
    MOMENTUM --> CORR[correlate_news asset_name articles]
    CORR --> CLUSTER[cluster_articles correlated news]

    CLUSTER --> CTX_CHECK{with_market_ctx\nand change_1d available?}
    CTX_CHECK -->|Yes| CTX[analyse_market_context]
    CTX_CHECK -->|No| CTX_NONE[market_ctx = None]

    CTX --> SIGNAL
    CTX_NONE --> SIGNAL

    SIGNAL[compute_signal_score\nmetrics momentum news\nmarket_ctx category] --> EXPLAIN[build_explanation]

    EXPLAIN --> STORAGE_CHECK{save=True\nand STORAGE_AVAILABLE?}
    STORAGE_CHECK -->|Yes| SNAP[_save_snapshot\nsilent on error]
    STORAGE_CHECK -->|No| SKIP_SNAP[Skip\ndashboard calls use save=False]

    SNAP --> HIST
    SKIP_SNAP --> HIST

    HIST[get_historical_features\nfrom stored snapshots] --> RETURN([Return full result dict])
```

---

## 15. Parallel Metrics Pre-fetch Pipeline

Note: `fetch_all_metrics_parallel` is defined in `pulseengine/core/app.py`, but the dashboard does **not** call it directly. The market heatmap and category overview are populated from `cached_scan_summary()` in `pulseengine/local/data.py`, which reads the pre-computed `_scan_summary.json.gz` written by the scan pipeline. The diagram below shows `fetch_all_metrics_parallel` for reference — it is available for external use but bypassed by the current dashboard flow.

```mermaid
flowchart TD
    CALL([fetch_all_metrics_parallel called\ndays=LOOKBACK_DAYS]) --> BUILDTASKS[Build task list\nall category+asset+ticker triples]

    BUILDTASKS --> POOL[ThreadPoolExecutor\nPRICE_FETCH_WORKERS threads]

    POOL --> WORKER[_fetch_one_asset\ncat name tkr days]

    WORKER --> FETCH[fetch_price_history ticker days]
    FETCH --> PMETRICS[compute_price_metrics]
    FETCH --> MMETRICS[compute_momentum_metrics]

    PMETRICS --> COLLECT
    MMETRICS --> COLLECT

    COLLECT[Collect result tuple\ncat name metrics momentum] --> MORE{More futures?}
    MORE -->|Yes| WORKER
    MORE -->|Done| ASSEMBLE

    ASSEMBLE[Assemble nested dict\ncategory -> asset -> metrics+momentum] --> RETURN([Return all_results dict])
```

---

## 16. Local Installer Pipeline

`install.py` is the main installer. `install.sh` (macOS/Linux) and `install.ps1` (Windows) are thin wrappers that detect a compatible Python interpreter and then hand off to `install.py` via `exec` / `&`.

```mermaid
flowchart TD
    WRAPPER([install.sh or install.ps1]) --> PYDETECT[Iterate candidate interpreter names\npython3.14 → python3.11 → python3 → python]
    PYDETECT --> FOUND{Compatible Python\n3.11–3.14 found?}
    FOUND -->|No| ABORT0([Exit 1 — install hint])
    FOUND -->|Yes| DELEGATE[exec / & install.py]

    DELEGATE --> ENTRY([install.py starts]) --> RECONFIGURE[Reconfigure stdout/stderr\nto UTF-8 on Windows]
    RECONFIGURE --> BANNER[Print banner]
    BANNER --> PY_CHECK[check_python_version\nverify 3.11 ≤ version ≤ 3.14]

    PY_CHECK --> PY_OK{In range?}
    PY_OK -->|No| ABORT1([sys.exit 1])
    PY_OK -->|Yes| VENV[create_venv\n.venv/ via python -m venv\nskip if already exists]

    VENV --> VENV_OK{Created or\nalready exists?}
    VENV_OK -->|Error| ABORT2([sys.exit 1\nwith stderr hint])
    VENV_OK -->|OK| DEPS[install_dependencies\nupgrade pip silently\nthen pip install -r requirements.txt]

    DEPS --> DEPS_OK{returncode == 0?}
    DEPS_OK -->|No| ABORT3([sys.exit 1\ncommon causes hint])
    DEPS_OK -->|Yes| VERIFY[verify_install\nimport each of 6 packages\nvia venv Python subprocess]

    VERIFY --> VER_OK{All 6 imports pass?}
    VER_OK -->|No| ABORT4([sys.exit 1])
    VER_OK -->|Yes| LAUNCH[generate_launch_script\nWindows: write launch.bat + launch.ps1\nmacOS/Linux: write launch.sh\nset chmod 755 on Unix]

    LAUNCH --> SUCCESS([print_success\nnext-steps message\nexit 0])
```
