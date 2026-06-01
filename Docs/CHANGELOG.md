# Changelog

All notable changes to this project will be documented in this file.

---

## [Unreleased]

### Fixed
- `_kw_re` in `pulseengine/core/signals.py` now applies a leading `\b` only when the keyword starts with an alphanumeric character. Previously the prefix was unconditional, so keywords beginning with a special character (e.g. a hypothetical `+term`) would generate an invalid boundary assertion. Suffix `\b` was already conditional; both guards are now symmetric.
- Neutral signal label in `compute_signal_score` (`pulseengine/core/signals.py`) now uses `>= SIGNAL_THRESHOLDS["neutral"]` instead of `>`, so a score exactly at the neutral boundary is correctly classified as Neutral rather than Slightly Bearish.
- `avg_signal_score` in `evaluate_signal_accuracy` (`pulseengine/core/backtest.py`) now computed as the mean of absolute scores, ensuring the reported average always reflects signal magnitude regardless of direction.

---

## [0.3.2] — 2026-05-18
### "UX Polish + Observability"

### Added
- Session-state navigation history stack in `pulseengine/local/dashboard.py`:
  - `_push_nav_if_changed()` — called on every rerun; detects changes in selected category, asset, or custom ticker and pushes a snapshot of the previous page state onto `st.session_state["_nav_history"]` (capped at 20 entries).
  - `_restore_nav_state(snapshot)` — writes a history snapshot back into session state and sets a `_nav_restoring` guard flag so the restore does not generate a spurious duplicate history entry on the next rerun.
  - `_on_back_click()` — `on_click` handler for the Back button; pops the most recent snapshot and calls `_restore_nav_state`.
  - Module-level tuples `_NAV_DETECT_KEYS` and `_NAV_SNAPSHOT_KEYS` defining which session-state keys constitute page identity and which are saved in each history snapshot.
- **← Back button** rendered fixed-positioned at the top-left of the main panel via a CSS `#pe-back-slot-marker` anchor span. Disabled when the history stack is empty; enabled as soon as the user has navigated away from the initial view. Implemented with `st.button("← Back", key="_back_btn_main", on_click=_on_back_click)`.
- Back button CSS in `pulseengine/local/styles.py`: a `:has(> * > #pe-back-slot-marker) + div` selector fixed-positions the button wrapper to `top: 60px; left: calc(21rem + 1rem)` with `z-index: 1000`, matching the sidebar default width and gutter.
- **Startup auto-refresh** — a `@st.fragment(run_every=5)` poller (`_scan_completion_poller`) runs in the background and triggers a full page rerun the moment the background scan thread finishes. This eliminates the stale-data banner-and-button pattern; instead, a quiet caption shows scan age and refresh status, and the UI updates automatically without user action.
- **Export & Offline placeholders** in the local dashboard sidebar under a "Export & Offline (Coming in v0.5)" expander — greyed-out Export to CSV and Export to PDF buttons so roadmap features are visible in the UI.

### Changed
- Replaced the stale-data banner + manual `Refresh now` button in `pulseengine/local/dashboard.py` with a compact age caption and the automatic `_scan_completion_poller` fragment.
- `pulseengine/core/errors.py` expanded: `_build_error_payload` moved from `app.py` into `errors.py` alongside the custom exception hierarchy so the helper is co-located with the types it acts on.
- Dead function and variable cleanup across `pulseengine/core/app.py`, `pulseengine/core/news.py`, `pulseengine/core/signals.py`, and `pulseengine/local/scan.py` — removed unused helpers and module-level variables that contributed to startup import time.
- Snapshot-save and historical-feature errors in `pulseengine/core/app.py` now logged at `WARNING` level instead of `DEBUG`.
- Skipped files with unparseable date strings in `pulseengine/core/storage.py` now emit a `DEBUG` log entry instead of silently passing.
- `except (ValueError, OSError)` in `pulseengine/core/storage.py` split into separate handlers; `OSError` now logs a `WARNING`.

### Fixed
- Variable shadowing in `_build_snapshot_price_cache` — the inner `ticker` loop variable shadowed the outer function parameter; renamed to avoid the collision.
- `_FakeVader.polarity_scores` in the test suite converted to a `@staticmethod`; `self` was unused, and the bound-method form triggered a linting warning.
- Test imports migrated from legacy shim paths (`src.*`, `app.*`, `config.settings`) to canonical `pulseengine.core.*` across `test_logic_coverage.py`, `test_optimisation.py`, `test_pipeline.py`, and `test_storage_and_scan.py`.
- Removed stale assertions on `signal_score` and `signal_label` duplicate keys that were dropped from the pipeline result schema.
- Duplicate warning icon removed from `st.warning` calls in `pulseengine/local/components.py` — icon was rendered both as inline text and via the `icon=` kwarg simultaneously.
- Signal legend in `render_signal_legend_sidebar()` now renders as a proper CommonMark bullet list instead of a single concatenated string.
- `source_weight` value removed from article card HTML in `pulseengine/local/components.py` — internal scoring metadata is no longer exposed in the UI.
- UTC timezone label added to the "Market data last updated" caption in the sidebar.
- Scan status now displays "overdue" instead of "~0 min" when the next scheduled scan is past due (`pulseengine/local/components.py`).
- Auto-scan disabled state in `pulseengine/local/dashboard.py` no longer shows a stale "queued" caption.
- `pulseengine/local/scan.py` now uses `dt.datetime.now(dt.UTC)` for a timezone-aware `scan_time` timestamp.
- `StorageError` added to the exception clause in `_snapshot_unchanged` in `pulseengine/core/storage.py`.

### Refactored
- All `Optional[X]` type annotations across `pulseengine/core/` replaced with the Python 3.10+ union syntax `X | None` (`context.py`, `explanation.py`, `news.py`, `price.py`, `signals.py`). No runtime behaviour changes.

### Notes
- Navigation history is scoped to `st.session_state` — it resets on page refresh but persists across asset switches within a single session.
- The `_scan_completion_poller` fragment runs every 5 seconds and exits after triggering one rerun; it does not poll indefinitely.
- No changes to the signal model, data pipeline, storage, or public API.

---

## [0.3.1] — 2026-04-26
### "Local Surface Migration"

### Changed
- `pulseengine/local/dashboard.py`, `components.py`, `styles.py`, `data.py` — replaced forward shims with the full production implementations. All imports updated from legacy shim paths (`app.*`, `config.*`, `dashboard.*`, `storage.*`) to canonical `pulseengine.core.*` and `pulseengine.core.config.*`.
- `pulseengine/local/scan.py` — replaced thin CLI wrapper with the full batch scan pipeline (previously only in `app/scan.py`). Now the canonical implementation; `app/scan.py` is a reverse shim.
- `dashboard/main.py` — converted from production script to reverse shim; re-executes `pulseengine/local/dashboard.py` so `streamlit run dashboard/main.py` still works unchanged.
- `dashboard/components.py`, `dashboard/styles.py`, `dashboard/data.py` — converted to reverse shims pointing to `pulseengine.local.*`.
- `app/scan.py` — converted to reverse shim; re-exports `run_scan` and `load_last_scan_summary` from `pulseengine.local.scan`.
- `tests/test_storage_and_scan.py` — updated mock patch target from `app.scan._save_summary` to `pulseengine.local.scan._save_summary` to reflect canonical module location.

### Added
- Export to CSV / PDF and Offline Mode placeholders added to the local dashboard sidebar (greyed-out buttons under "Export & Offline (Coming in v0.5)" expander). Roadmap-listed features are no longer silently absent from the UI.

### Notes
- `python -m app.scan` and `streamlit run dashboard/main.py` remain functional via the reverse shims for backward compatibility.
- Canonical scan CLI: `python -m pulseengine.local.scan`
- No logic, signal model, or API changes. Pure structural migration completing the v0.3 repo restructure.

---

## [0.3.0] — 2026-04-22
### "Foundation Split + Arbitrary Tickers"

### Added
- `pulseengine/` top-level package with three sub-surfaces:
  - `pulseengine/core/` — shared headless engine (`app.py`, `config.py`, `storage.py`, `backtest.py`, `price.py`, `news.py`, `signals.py`, `context.py`, `explanation.py`, `sentiment.py`, `errors.py`). Imported by both `local/` and `web/`.
  - `pulseengine/local/` — full-featured local app surface (`dashboard.py`, `scan.py`, `components.py`, `styles.py`, `data.py`). Supports file I/O, backtest, snapshot storage, and arbitrary ticker analysis.
  - `pulseengine/web/` — restricted stateless demo surface (`dashboard.py`). No file I/O, no local model inference, no persistent state.
- Arbitrary ticker lookup wired end-to-end: users can enter any valid Yahoo Finance ticker in the sidebar; `generate_keywords` in `pulseengine.core.news` auto-generates keyword coverage; low-news-confidence safeguards apply when coverage is sparse.
- `install.py`: Cross-platform local installer — verifies Python version (3.11–3.14), creates `.venv/` via `python -m venv`, installs `requirements.txt` inside it, verifies all six key package imports, and generates a platform-appropriate launch script (`launch.bat` + `launch.ps1` on Windows, `launch.sh` on macOS/Linux).
- `install.sh`: macOS/Linux convenience wrapper that detects a compatible Python 3.11–3.14 interpreter across common command names and delegates to `install.py`.
- `install.ps1`: Windows PowerShell wrapper with equivalent Python detection, including a `py` launcher fallback for specific minor versions, then delegates to `install.py`.
- `.vscode/launch.json`: VS Code debug/run configurations for all five entry points (Dashboard, Scan Dry Run, Scan Full, Analysis CLI, Tests).
- `.idea/runConfigurations/`: PyCharm run/debug configurations for the same five entry points, compatible with both Community and Professional editions.
- `CONTRIBUTING.md` **IDE Setup** section documenting how to use the shared configurations in VS Code and PyCharm.
- Backward-compat shim packages (`app/`, `dashboard/`, `src/`, `config/`, `storage/`) re-export from the new canonical locations so existing scripts and imports continue to work without changes.

### Fixed
- `install.ps1`: `$PyVersion` was never initialized before use, causing a `StrictMode` exception on the common path where Python was found via the normal candidate loop — the script crashed before ever reaching `install.py`.
- `install.py`: Double curly braces (`{{`/`}}`) in the generated `launch.ps1` content string wrote literal `{{` and `}}` to disk (a regular string, not an f-string), producing invalid PowerShell block syntax.
- `install.py`: `UnicodeEncodeError` crash on Windows `cp1252` consoles when printing the box-drawing banner characters — stdout/stderr are now reconfigured to UTF-8 at startup.

### Changed
- Canonical entry points changed:
  - Dashboard: `streamlit run pulseengine/local/dashboard.py`
  - Web demo: `streamlit run pulseengine/web/dashboard.py`
  - Scan CLI: `python -m pulseengine.local.scan`
  - Legacy entry points (`dashboard/main.py`, `python -m app.scan`) remain as backward-compat shims.
- `.gitignore` updated to ignore `launch.bat`, `launch.ps1`, and `launch.sh` (installer-generated artifacts) and to unignore `.vscode/launch.json` and `.idea/runConfigurations/`.
- `CONTRIBUTING.md` **Pull Request Process** "Do not commit" list updated to allow the new IDE config paths and clarify which IDE files remain excluded.
- `README.md` updated throughout to reflect new canonical entry points, module paths, and project structure.
- `Docs/code_flow.md` updated: all module badges, diagram entry points, and prose references updated from old flat layout to `pulseengine/core/`, `pulseengine/local/`, `pulseengine/web/`.
- `Docs/ROADMAP.md` v0.3 section updated to mark repo restructure complete.
- Test count: 54 passing (up from 42 in v0.2.3).

---

## [0.2.3] - 2026-04-14
### "Ticker Keyword Intelligence + Correlation Reliability"

### Added
- `generate_keywords(ticker)` in `src/news.py` for arbitrary ticker support groundwork:
  - pulls Yahoo Finance metadata via `yfinance`
  - includes ticker symbol, company name tokens, and top executive surnames
  - removes duplicate and short tokens (`< 3` chars)
  - excludes broad corporate suffix noise (`inc`, `corp`, `group`, etc.)
  - bounded by `REQUEST_TIMEOUT` using a daemon thread so hung metadata calls cannot block the pipeline
  - graceful fallback to `[ticker]` for timeout, network failure, or unknown symbols
- `Docs/CONTRIBUTORS.md` added to document acknowledged contributors.
- 5 focused tests added in `tests/test_core.py`:
  - `generate_keywords` known ticker path
  - unknown ticker fallback path
  - network failure fallback path
  - timeout fallback path
  - `correlate_news` regression guard against substring false positives
- Test suite count increased to 42.

### Fixed
- `correlate_news` in `src/signals.py` now uses word-boundary regex matching (`\b{kw}\b` via `_kw_re`) instead of plain substring containment (`kw in blob`). This removes false-positive matches where short keywords were only present as substrings (for example, `gold` matching `goldman`).
- Dashboard stale-data handling in `dashboard/main.py` changed from automatic stale-triggered reruns to explicit user action (`Refresh now`), reducing involuntary refresh loops.
- Dashboard refresh epoch increments now use session-state source of truth to avoid stale local increments during refresh/scan actions.

### Changed
- Sidebar now includes `Enable auto background scan` toggle in `dashboard/main.py`, allowing contributors/users to disable scan auto-trigger behavior during interactive sessions.
- Background scan refresh and manual refresh flows were aligned to use consistent state updates before rerun.
- CI workflow concurrency policy in `.github/workflows/ci.yml` updated to preserve all `main` branch runs (only non-main runs are canceled in-progress), keeping branch checks reliable during rapid pushes.

### Documentation
- `Docs/code_flow.md` expanded with the keyword generation pipeline and updated news-correlation matching flow notes.
- `Docs/variable_list.md` extended with new symbols/constants (`generate_keywords`, `_CORP_SUFFIXES`, `_KW_PATTERN_CACHE`, `_kw_re`) and updated correlation behavior references.
- `README.md` improvements:
  - fixed disclaimer badge/doc links
  - added Docker quick-start TOC entry
  - normalized scan invocation to module form (`python -m app.scan`)
  - added contributors document references
- `CONTRIBUTING.md` updated to use module-form scan commands (`python -m app.scan --dry-run`) for consistency with package layout.

### Technical
- `_KW_PATTERN_CACHE` introduced in `src/signals.py` to reuse compiled regex patterns across correlation calls, reducing repeated regex compilation overhead.
- `_kw_re` helper added to centralize safe keyword pattern construction.
- Industry and sector fields intentionally excluded from `generate_keywords` output because broad labels (for example, `Technology`) create noisy cross-asset matches.

---

## [0.2.2] - 2026-04-12
### "Dashboard Stability + Security + Test Expansion"

### Added
- `tests/test_logic_coverage.py` — edge case coverage for signal scoring, sentiment, deduplication, and contradiction detection
- `tests/test_storage_and_scan.py` — storage round-trip, retention policy, dry-run scan, and synthetic backtest tests
- Signal score legend added to the sidebar for quick reference
- Loading spinner shown in the dashboard while live analysis is running

### Changed
- Pinned runtime dependencies tightened after `pip audit` security review; no vulnerable packages remain in `requirements.txt`
- Dashboard cache invalidation logic reduced to avoid unnecessary reruns on stale data
- Dashboard stale-refresh handling tightened — refresh now triggers only when data is genuinely outdated
- Signal legend copy in sidebar clarified for readability
- Changelog housekeeping updated on `main` after sync

### Technical
- Total test count increased from 14 to 37
- All test files use package-based imports consistent with the v0.2.1 modular restructure

---

## [0.2.1] - 2026-04-07
### "Modular Package Restructure + Asset Organisation"
> Partial progress toward v0.3. Arbitrary ticker support, local installer, and open issue backlog (#10, #11, #12) remain outstanding before v0.3.0 is reached.

### Changed
- Reorganized all top-level Python files into proper packages with `__init__.py` files:
  - `app.py` → `app/analysis.py`
  - `scan.py` → `app/scan.py`
  - `backtest.py` → `app/backtest.py`
  - `dashboard.py` → `dashboard/main.py`
  - `ui_components.py` → `dashboard/components.py`
  - `styles.py` → `dashboard/styles.py`
  - `dashboard_data.py` → `dashboard/data.py`
  - `storage.py` → `storage/storage.py`
  - `config.py` → `config/settings.py`
- All import statements updated to use absolute package-based imports (e.g. `from config.settings import X`, `from storage.storage import X`)
- `config/settings.py` `BASE_DIR` updated to use `.parent.parent` to correctly resolve the project root from the new subdirectory location
- Moved image assets out of the project root into dedicated subdirectories:
  - `favicon.ico` → `assets/icons/favicon.ico`
  - `pulseengine_logo.png` → `assets/logo/pulseengine_logo.png`
- Dashboard entry point changed from `streamlit run dashboard.py` to `streamlit run dashboard/main.py`
- Scan CLI entry point changed from `python scan.py` to `python -m app.scan`

### Fixed
- Added `sys.path.insert(0, ...)` at the top of `dashboard/main.py` to ensure the project root is on `sys.path` when Streamlit is launched, resolving `ModuleNotFoundError: No module named 'config'` that occurred because Streamlit adds the script directory (`dashboard/`) to `sys.path` rather than the project root

### Technical
- No logic, function names, arguments, or behaviour changed — pure structural reorganization
- `src/` package (engine, price, news, signals, context, explanation, sentiment) remains unchanged in location; only its `from config import` statements updated to `from config.settings import`

---

## [0.2.0] - 2026-04-04
### "UI Overhaul + Performance & Scalability Improvements"

## Added
- Easter egg functionality in the UI.

### Changed
- Complete dashboard UI redesign with a retro financial aesthetic (cards, typography, layout, sidebar, and visual hierarchy)
- Improved structure of signal, explanation, contradiction, and news sections for faster readability

### Improved
- Reduced load times via parallel data fetching and scan-level reuse of news data
- Improved performance under higher user load through more efficient execution and reduced redundant processing
- Optimized storage layer with compressed snapshots, atomic writes, and noise-threshold updates
- Improved stability when price or news data is missing

### Technical
- Centralized configuration handling to reduce repeated computation and improve consistency
- Internal optimizations to support better scalability during peak usage


## [0.1.1] — 2026-04-03

### Added
- Minimal `pytest` test suite (`tests/test_core.py`, `tests/test_pipeline.py`) — 14 tests covering core function invariants and pipeline smoke tests
- `requirements-dev.txt` for test dependencies (`pytest`, `pytest-mock`)
- `tests/MAINTENANCE.md` — guide for when and how to update the test suite

### Changed
- `tests/conftest.py` rewritten — removed import facade and future-proofing logic; now contains only fixtures and shared setup
- `pytest.ini` simplified — removed stale `hyper` marker and filter
- `CONTRIBUTING.md` — Testing section updated to reflect the live pytest suite; dev setup now includes `requirements-dev.txt` install step; "Automated tests" removed from open contribution areas and replaced with "Test suite expansion"
- `README.md` — Project Structure updated to include `tests/` directory and `requirements-dev.txt`

### Removed
- 9 over-engineered placeholder test files (`test_backtest.py`, `test_dedup_and_clustering.py`, `test_hyper.py`, `test_integration.py`, `test_momentum.py`, `test_price_metrics.py`, `test_sentiment.py`, `test_signal_score.py`, `test_storage.py`)
- Unused dependencies from `requirements.txt`: `beautifulsoup4`, `soupsieve`, `GitPython`, `gitdb`, `smmap`, `peewee`
- Dev dependencies duplicated at the bottom of `requirements.txt` (`freezegun`, `pytest`, `pytest-mock`)
- `freezegun` from `requirements-dev.txt` — no tests use time-freezing

## [0.1.0] — 2026-04-02

### Added
- Core analysis engine (`app.py`) — price metrics, news correlation, composite signal scoring
- Streamlit dashboard (`dashboard.py`) — wide layout, 90s auto-refresh, background scan management
- Background scan daemon — full 24-asset scan every 30 minutes without blocking the UI
- Batch scan pipeline (`scan.py`) — supports `--dry-run` and `--quiet` flags
- Compressed snapshot storage (`storage.py`) — gzip JSON with tiered retention (7 / 30 / 60 days)
- Backtesting module (`backtest.py`) — hit-rate evaluation by signal strength and label
- Configuration module (`config.py`) — all tunable constants in one place
- 24 tracked assets across Commodities, Cryptocurrency, Tech Stocks, and Market Indices
- 12 RSS feed sources with parallel fetch and Jaccard deduplication
- VADER sentiment engine with injected financial lexicon
- 8 event category detection (central bank, geopolitical, earnings, etc.)
- Per-asset-class signal weighting profiles
- `Dockerfile` and `.dockerignore` for containerised deployment
- Fully pinned `requirements.txt` via `pip freeze`
