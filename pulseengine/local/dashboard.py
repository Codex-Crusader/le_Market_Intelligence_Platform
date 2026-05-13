"""
dashboard.py — PulseEngine local controller.

Responsible for:
  • page configuration
  • scan lifecycle orchestration (background thread management)
  • layout flow and sidebar wiring
  • loading data and passing it to UI components

Run with:  streamlit run pulseengine/local/dashboard.py

Decision flow (top to bottom):
  Signal  ->  Why it matters  ->  Primary driver  ->  Contradictions / risks
  ->  Metric cards  ->  Momentum  ->  Top news clusters  ->  Price chart
  ->  Backtest summary  ->  Full analysis  ->  Market heatmap
  ->  Category overview
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the project root is on sys.path so package imports work
# regardless of which directory streamlit is launched from.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import datetime as dt
import logging
import re
import threading
import time

import streamlit as st

import pulseengine.local.components as ui
from pulseengine.core import (
    DASHBOARD_ICON,
    DASHBOARD_LAYOUT,
    DASHBOARD_TITLE,
    DEFAULT_CATEGORY,
    PRICE_CHANGE_THRESHOLD,
    STORAGE_DIR,
    TRACKED_ASSETS,
    VADER_AVAILABLE,
    correlate_news,
    get_display_clusters,
)
from pulseengine.core.config import (
    NEWS_CACHE_TTL,
    PRICE_CACHE_TTL,
    REQUEST_TIMEOUT,
    SCAN_INTERVAL_MINUTES,
)
from pulseengine.local.data import (
    cached_generated_keywords,
    cached_live_analysis,
    cached_news,
    cached_scan_summary,
    is_data_stale,
)
from pulseengine.local.styles import load_css

log = logging.getLogger(__name__)

# Streamlit's root logger defaults to WARNING, which silently drops every
# log.info() call from the scan pipeline.  Attach a dedicated StreamHandler
# to the "pulseengine" logger so scan progress reaches the terminal regardless
# of Streamlit's logging configuration.  propagate=False prevents double-
# printing if a root handler is also present (e.g. when running via CLI).
_pe_log = logging.getLogger("pulseengine")
if not _pe_log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    ))
    _pe_log.addHandler(_h)
    _pe_log.propagate = False
_pe_log.setLevel(logging.INFO)


# ── Page configuration ─────────────────────────────────────────────────────────

st.set_page_config(
    page_title=DASHBOARD_TITLE,
    page_icon=DASHBOARD_ICON,
    layout=DASHBOARD_LAYOUT,  # type: ignore[arg-type]
)

load_css()


_TICKER_INPUT_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-=^]{0,14}$")


def _normalize_ticker_input(raw: str) -> str:
    """Return a normalized Yahoo ticker symbol, or empty string if invalid."""
    val = (raw or "").strip().upper()
    return val if _TICKER_INPUT_RE.fullmatch(val) else ""


def _ticker_exists(symbol: str) -> bool:
    _result: list = [False]

    def _check() -> None:
        try:
            import yfinance as yf
            _result[0] = bool(getattr(yf.Ticker(symbol).fast_info, "currency", None))
        except Exception as exc:  # yfinance raises inconsistently across versions/networks
            log.debug("_ticker_exists(%r): %s", symbol, exc)

    t = threading.Thread(target=_check, daemon=True)
    t.start()
    t.join(timeout=REQUEST_TIMEOUT)
    return _result[0]


# ── Scan orchestration ─────────────────────────────────────────────────────────

@st.cache_resource
def _get_scan_state() -> dict:
    """Singleton scan state — created once per process, never reset by reruns."""
    return {
        "lock":          threading.Lock(),
        "running":       False,
        "last_started":  0.0,
        "last_finished": 0.0,
        "error":         "",
        "assets_done":   0,
        "errors_count":  0,
    }


def _scan_summary_mtime() -> float:
    """Return mtime of the scan summary file, or 0.0 when absent."""
    p = Path(STORAGE_DIR) / "_scan_summary.json.gz"
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _run_background_scan() -> None:
    """Worker executed inside a daemon thread."""
    state = _get_scan_state()
    state["running"]     = True
    state["error"]       = ""
    state["assets_done"] = 0
    state["errors_count"] = 0
    try:
        from pulseengine.local.scan import run_scan
        summary = run_scan(verbose=True)
        state["assets_done"] = summary.get("succeeded", 0)
        state["errors_count"] = len(summary.get("errors", []))
    except Exception as exc:
        state["error"] = str(exc)
    finally:
        state["running"]       = False
        state["last_finished"] = time.time()
        state["lock"].release()


def _maybe_trigger_scan() -> None:
    """Called on every dashboard rerun. Starts a background scan when stale."""
    now   = time.time()
    state = _get_scan_state()

    if now - st.session_state.get("_scan_check_ts", 0.0) < 60.0:
        return
    st.session_state["_scan_check_ts"] = now

    if now - _scan_summary_mtime() < SCAN_INTERVAL_MINUTES * 60:
        return

    if not state["lock"].acquire(blocking=False):
        return

    state["last_started"] = now
    state["running"]      = True
    st.session_state["_scan_rerun_done"] = False
    threading.Thread(
        target=_run_background_scan,
        daemon=True,
        name="full-market-scan",
    ).start()


@st.fragment(run_every=5)
def _poll_scan_completion() -> None:
    """Polls every 5 s while a scan is running and triggers a full page rerun on completion."""
    state = _get_scan_state()
    if (
        not state["running"]
        and state.get("last_finished", 0) > 0
        and not st.session_state.get("_scan_rerun_done", False)
    ):
        st.session_state["_scan_rerun_done"] = True
        st.session_state["_scan_refresh_epoch"] = int(st.session_state.get("_scan_refresh_epoch", 0)) + 1
        st.rerun(scope="app")


# ── Navigation history ─────────────────────────────────────────────────────────

# Keys that trigger a history push when they change (the "page identity").
_NAV_DETECT_KEYS = ("_selected_category", "_selected_asset", "_confirmed_custom_ticker")
# Keys saved in each snapshot (includes lazy-load state so Back restores it).
_NAV_SNAPSHOT_KEYS = (*_NAV_DETECT_KEYS, "_news_for", "_live_for", "_custom_ticker_input")


def _push_nav_if_changed() -> None:
    """Push a snapshot of the previous page to history when navigation occurred."""
    # If we're mid-restore, just clear the flag and skip — the restored state
    # is already the truth; pushing it would create a spurious duplicate entry.
    if st.session_state.get("_nav_restoring"):
        st.session_state["_nav_restoring"] = False
        return
    last = st.session_state.get("_last_nav_snapshot")
    current = {k: st.session_state.get(k) for k in _NAV_SNAPSHOT_KEYS}
    if last is not None and any(last.get(k) != current.get(k) for k in _NAV_DETECT_KEYS):
        history: list = st.session_state.setdefault("_nav_history", [])
        history.append(last)
        if len(history) > 20:
            history.pop(0)
    st.session_state["_last_nav_snapshot"] = current


def _restore_nav_state(snapshot: dict) -> None:
    """Write a history snapshot back into session_state and flag the restore."""
    st.session_state["_nav_restoring"] = True
    for k, v in snapshot.items():
        if v is None:
            st.session_state.pop(k, None)
        else:
            st.session_state[k] = v


st.sidebar.checkbox(
    "Enable auto background scan",
    value=True,
    key="_enable_auto_scan"
)

if st.session_state.get("_enable_auto_scan", True):
    _maybe_trigger_scan()

_scan_state = _get_scan_state()

# While a scan is running, poll every 5 s for completion and trigger a full page rerun.
if _scan_state["running"]:
    _poll_scan_completion()

# Fallback: handles completion detected on the next user-triggered rerun (e.g. if the
# dashboard was closed and reopened after the scan finished without the fragment active).
if (
    not _scan_state["running"]
    and _scan_state.get("last_finished", 0) > 0
    and not st.session_state.get("_scan_rerun_done", False)
):
    st.session_state["_scan_rerun_done"] = True
    st.session_state["_scan_refresh_epoch"] = int(st.session_state.get("_scan_refresh_epoch", 0)) + 1
    st.rerun()



# Load scan summary once per run — needed for scan status display and main content.
_scan_refresh_epoch = int(st.session_state.get("_scan_refresh_epoch", 0))
_summary         = cached_scan_summary(_scan_refresh_epoch)
_summary_results = _summary.get("results", {})
_summary_date    = _summary.get("scan_date", "")


def _build_snapshot_price_cache(summary_results: dict) -> tuple[tuple[str, float], ...]:
    """Build a hashable {ticker: change_1d} cache from the latest snapshot."""
    cache_items: list[tuple[str, float]] = []
    for category, assets in TRACKED_ASSETS.items():
        category_rows = summary_results.get(category, {}) if isinstance(summary_results, dict) else {}
        for asset_name, sym in assets.items():
            change_1d = category_rows.get(asset_name, {}).get("change_1d")
            if change_1d is not None:
                cache_items.append((sym, float(change_1d)))
    return tuple(cache_items)


_snapshot_price_cache = _build_snapshot_price_cache(_summary_results)

# ── Sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.markdown(ui.sidebar_header_html(), unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.markdown("**Ticker Lookup**")
custom_ticker_raw = st.sidebar.text_input(
    "Ticker symbol (e.g. PLTR, ARM, TSM)",
    key="_custom_ticker_input",
    placeholder="e.g. PLTR, ARM, TSM, BRK-B",
)
custom_ticker = _normalize_ticker_input(custom_ticker_raw)
if not custom_ticker_raw.strip():
    st.session_state.pop("_confirmed_custom_ticker", None)
    st.session_state.pop("_ticker_invalid", None)
if custom_ticker_raw.strip() and not custom_ticker:
    st.sidebar.warning(
        "Invalid ticker format. Use letters/numbers and optional ., -, ^, = characters.",
        icon="⚠️",
    )

_col1, _col2 = st.sidebar.columns(2)
if _col1.button("Analyse", disabled=not bool(custom_ticker)):
    with st.spinner(f"Validating {custom_ticker} …"):
        if _ticker_exists(custom_ticker):
            st.session_state["_confirmed_custom_ticker"] = custom_ticker
            st.session_state.pop("_ticker_invalid", None)
        else:
            st.session_state["_confirmed_custom_ticker"] = ""
            st.session_state["_ticker_invalid"] = custom_ticker
    st.rerun()
if _col2.button("Clear", disabled=not bool(custom_ticker_raw.strip())):
    st.session_state["_custom_ticker_input"] = ""
    st.session_state["_confirmed_custom_ticker"] = ""
    st.session_state.pop("_ticker_invalid", None)
    st.rerun()

_invalid_sym = st.session_state.get("_ticker_invalid", "")
if _invalid_sym:
    st.sidebar.error(
        f"No data found for **{_invalid_sym}**. Check the ticker symbol and try again."
    )

st.sidebar.markdown("---")

# Detect navigation changes and maintain history, then render the Back button.
_push_nav_if_changed()
_nav_history: list = st.session_state.get("_nav_history", [])


def _on_back_click() -> None:
    # on_click runs between reruns — before any widgets are instantiated —
    # so writing widget-backed keys here is always safe.
    history: list = st.session_state.get("_nav_history", [])
    if not history:
        return
    snapshot = history.pop()
    st.session_state["_nav_history"] = history
    _restore_nav_state(snapshot)



_confirmed = st.session_state.get("_confirmed_custom_ticker", "")
using_custom_ticker = bool(_confirmed)

# Always render category/asset selectors so the sidebar layout is stable.
# When a custom ticker is active they are disabled and their values unused.
categories = list(TRACKED_ASSETS.keys())
default_cat_idx = categories.index(DEFAULT_CATEGORY) if DEFAULT_CATEGORY in categories else 0
selected_category = (
    st.sidebar.selectbox(
        "Category", categories, index=default_cat_idx,
        key="_selected_category", disabled=using_custom_ticker,
    )
    or categories[0]
)

asset_names = list(TRACKED_ASSETS[selected_category].keys())
if not asset_names:
    st.error(f"No assets configured for category: {selected_category}")
    st.stop()
# Guard: if a restored asset value isn't valid for the current category, drop it.
if st.session_state.get("_selected_asset") not in asset_names:
    st.session_state.pop("_selected_asset", None)
selected_asset = (
    st.sidebar.selectbox(
        "Asset", asset_names, key="_selected_asset", disabled=using_custom_ticker,
    )
    or asset_names[0]
)

if using_custom_ticker:
    selected_category = "Custom Ticker"
    selected_asset = _confirmed
    ticker = _confirmed
else:
    ticker = TRACKED_ASSETS[selected_category][selected_asset]

st.sidebar.markdown("---")

run_context = st.sidebar.checkbox(
    "Enable market-context analysis",
    value=False,
    help="Compares against sector peers and benchmark. Slower but deeper.",
)
if using_custom_ticker and run_context:
    st.sidebar.caption(
        "Market-context analysis is skipped for custom tickers unless peers are configured."
    )

st.sidebar.markdown("---")

# ── Coming-soon placeholders (v0.5 features) ──────────────────────────────────
with st.sidebar.expander("Export & Offline (Coming in v0.5)", expanded=False):
    st.button("Export to CSV", disabled=True, help="Coming in v0.5")
    st.button("Export to PDF", disabled=True, help="Coming in v0.5")
    st.button("Enable Offline Mode", disabled=True, help="Coming in v0.5 — caches data for offline use")
    st.caption("These features are planned for v0.5. Local Intelligence update.")

st.sidebar.markdown("---")
st.sidebar.caption(f"Ticker: `{ticker}`")
st.sidebar.caption(f"Prices refresh: every {PRICE_CACHE_TTL}s")
st.sidebar.caption(f"News refresh: every {NEWS_CACHE_TTL}s")
st.sidebar.caption(f"Sentiment engine: {'VADER' if VADER_AVAILABLE else 'Keyword fallback'}")
st.sidebar.caption(f"Page rendered: {dt.datetime.now().strftime('%H:%M:%S')}")

if st.sidebar.button("Refresh Data"):
    st.session_state["_scan_refresh_epoch"] = st.session_state.get("_scan_refresh_epoch", 0) + 1
    st.session_state.pop("_stale_refresh_triggered", None)
    st.rerun()

# Scan status display + manual trigger
st.sidebar.markdown("---")
_scan_state = _get_scan_state()
ui.render_scan_status_sidebar(_scan_state, _summary)
ui.render_signal_legend_sidebar()

if st.sidebar.button(
    "Run full scan now",
    disabled=_scan_state["running"],
    help=f"Scans all {sum(len(v) for v in TRACKED_ASSETS.values())} tracked assets and saves snapshots",
):
    if not _scan_state["running"] and _scan_state["lock"].acquire(blocking=False):
        _scan_state["last_started"] = time.time()
        _scan_state["running"]      = True
        st.session_state["_scan_refresh_epoch"] = st.session_state.get("_scan_refresh_epoch", 0) + 1
        st.session_state["_scan_rerun_done"] = False
        threading.Thread(
            target=_run_background_scan,
            daemon=True,
            name="full-market-scan-manual",
        ).start()
    st.rerun()

# Top movers
st.sidebar.markdown("---")
st.sidebar.markdown("**Top Movers — 24h**")
with st.sidebar:
    _top_movers = _summary.get("top_movers", {})
    ui.render_mover_rows(
        _top_movers.get("gainers", []),
        _top_movers.get("losers", []),
        _summary_date,
    )

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Data sources (free, public):**  \n"
    "Yahoo Finance · Reuters · CNBC  \n"
    "BBC · CoinDesk · Google News  \n"
    "NPR · MarketWatch · Al Jazeera"
)


# ── Main panel ─────────────────────────────────────────────────────────────────

# The span below is an invisible CSS anchor. The immediately-following div
# (rendered by st.button) is targeted by a :has() sibling selector in styles.py
# and fixed-positioned to the top-left corner of the viewport.
st.markdown('<span id="pe-back-slot-marker"></span>', unsafe_allow_html=True)
st.button(
    "← Back",
    key="_back_btn_main",
    disabled=not _nav_history,
    help="Return to the previous asset you were viewing",
    on_click=_on_back_click,
)

_stale = is_data_stale(_summary)
if _stale:
    _scan_time = _summary.get("scan_time", "")
    _age_str = ""
    if _scan_time:
        try:
            _last = dt.datetime.fromisoformat(_scan_time)
            if _last.tzinfo is None:
                _last = _last.replace(tzinfo=dt.UTC)
            _age_secs = int((dt.datetime.now(dt.UTC) - _last).total_seconds())
            if _age_secs < 3600:
                _age_str = f"{_age_secs // 60}m ago"
            elif _age_secs < 86400:
                _age_str = f"{_age_secs // 3600}h ago"
            else:
                _age_str = f"{_age_secs // 86400}d ago"
        except (ValueError, TypeError):
            pass
    _refresh_status = "refreshing in background" if _scan_state["running"] else "background refresh queued"
    _label = f"last scan {_age_str} · {_refresh_status}" if _age_str else _refresh_status
    st.caption(f"Showing older data — {_label}")

st.markdown(f"# {selected_asset}")
st.caption(f"{selected_category}  ·  `{ticker}`  ·  last 30 days")

ui.render_data_status_banner(_scan_state, _stale, _summary)

snap = (
    _summary_results.get(selected_category, {}).get(selected_asset, {})
    if selected_category in TRACKED_ASSETS
    else {}
)
chg_1d         = snap.get("change_1d")
is_significant = chg_1d is not None and abs(chg_1d) >= PRICE_CHANGE_THRESHOLD

_live_loaded = st.session_state.get("_live_for") == ticker
_news_loaded = st.session_state.get("_news_for") == ticker
_custom_keywords = (
    cached_generated_keywords(ticker)
    if using_custom_ticker and (_news_loaded or _live_loaded)
    else None
)


# SECTION 1-3 — snapshot data (tracked assets only; custom tickers go straight to live analysis)
if not using_custom_ticker:
    ui.render_signal_card(snap, selected_category, selected_asset, chg_1d, is_significant)
    ui.render_why_box(snap)
    st.markdown("---")
    ui.render_snapshot_metrics(snap, chg_1d)
else:
    # Kick off live data loading immediately so the analysis panel renders on the next rerun
    # without requiring the user to open the expander and click a second button.
    if not _live_loaded:
        st.session_state["_live_for"] = ticker
        st.rerun()

# SECTION 4 — Related news (deferred behind explicit user action)
st.markdown("---")
if not _news_loaded:
    st.markdown("### Related News")
    if st.button("Load news feed", key="_news_btn"):
        st.session_state["_news_for"] = ticker
        st.rerun()
    st.caption("News is not fetched on startup. Click above to load from 12 RSS feeds.")
else:
    articles   = cached_news()
    news       = correlate_news(selected_asset, articles, keywords=_custom_keywords)
    disp_clust = get_display_clusters(news, max_clusters=2)
    ui.render_news_section(
        disp_clust["clusters"],
        disp_clust["suppressed_count"],
        len(news),
        news,
    )

# SECTION 5 — Price chart & live analysis (deferred behind expander)
st.markdown("---")
with st.expander("Price Chart & Live Analysis", expanded=using_custom_ticker):
    if not _live_loaded:
        st.caption(
            "Live price history and deep analysis are not fetched on startup. "
            "Loads 30-day OHLCV from Yahoo Finance and recomputes all signal components."
        )
        if st.button("Load live data", key="_live_btn"):
            st.session_state["_live_for"] = ticker
            st.rerun()
    else:
        with st.spinner("Loading live analysis ..."):
            live_result = cached_live_analysis(
                selected_asset,
                ticker,
                selected_category,
                _news_loaded,
                run_context,
                scan_token=_scan_refresh_epoch,
                keywords=tuple(_custom_keywords or ()),
                price_cache_items=_snapshot_price_cache,
            )

        if live_result.get("error"):
            st.error(live_result["error"])
        else:
            ui.render_live_analysis(
                live_result["history"],
                selected_asset,
                live_result["signal"],
                live_result["explanation"],
                snap,
                is_significant,
            )

# SECTION 13 — Market heatmap
st.markdown("---")
st.markdown("## Market Heatmap — 24h Changes")
ui.render_heatmap(_summary, _summary_date)

# SECTION 14 — Category overview
st.markdown("---")
with st.expander("Category Overview", expanded=False):
    if selected_category in TRACKED_ASSETS:
        _cat_data = _summary.get("category_rows", {}).get(selected_category, {})
        ui.render_category_overview(_cat_data, _summary_date)
    else:
        st.info("Category overview is only available for the 24 tracked assets.")


# ── Footer ─────────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption(
    "PulseEngine  ·  "
    "Yahoo Finance (prices) + Public RSS (news) + VADER (sentiment)  ·  "
    "This is not financial advice."
)


# ── Easter egg ─────────────────────────────────────────────────────────────────
_EGG_LIMIT  = 5
_EGG_WINDOW = 2.0
_EGG_URL    = "https://www.youtube.com/watch?v=QDia3e12czc"

if "_egg_clicks" not in st.session_state:
    st.session_state["_egg_clicks"] = []

clicked = st.button("·", key="_egg_btn", help="", type="tertiary")
_now    = time.time()

if clicked:
    st.session_state["_egg_clicks"].append(_now)

st.session_state["_egg_clicks"] = [
    t for t in st.session_state["_egg_clicks"]
    if _now - t <= _EGG_WINDOW
]

if len(st.session_state["_egg_clicks"]) >= _EGG_LIMIT:
    st.session_state["_egg_clicks"] = []
    st.link_button("Easter Egg Unlocked!", _EGG_URL)
