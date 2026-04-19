"""
dashboard.py — PulseEngine controller.

Responsible for:
  • page configuration
  • scan lifecycle orchestration (background thread management)
  • layout flow and sidebar wiring
  • loading data and passing it to UI components

Run with:  streamlit run dashboard/main.py

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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import datetime as dt
import logging
import re
import threading
import time

import pandas as pd
import streamlit as st

from config.settings import (
    TRACKED_ASSETS,
    DASHBOARD_TITLE,
    DASHBOARD_ICON,
    DASHBOARD_LAYOUT,
    DEFAULT_CATEGORY,
    NEWS_CACHE_TTL,
    PRICE_CACHE_TTL,
    PRICE_CHANGE_THRESHOLD,
    SCAN_INTERVAL_MINUTES,
    STORAGE_DIR,
)
from app.analysis import (
    VADER_AVAILABLE,
    correlate_news,
    get_display_clusters,
    compute_price_metrics,
    compute_momentum_metrics,
    compute_signal_score,
    build_explanation,
    analyse_market_context,
)
from src.errors import DataFetchError
from dashboard.data import (
    cached_generated_keywords,
    cached_news,
    cached_history,
    cached_scan_summary,
    is_data_stale,
)
from dashboard.styles import load_css
import dashboard.components as ui

log = logging.getLogger(__name__)


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
    try:
        import yfinance as yf
        return bool(getattr(yf.Ticker(symbol).fast_info, "currency", None))
    except (OSError, ValueError, KeyError):
        return False


# ── Scan orchestration ─────────────────────────────────────────────────────────

@st.cache_resource
def _get_scan_state() -> dict:
    """
    Singleton scan state — created once per process, never reset by reruns.
    """
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
        from app.scan import run_scan
        summary = run_scan(verbose=False)
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



st.sidebar.checkbox(
    "Enable auto background scan",
    value=True,
    key="_enable_auto_scan"
)

if st.session_state.get("_enable_auto_scan", True):
    _maybe_trigger_scan()
# Rerun once after a background scan completes so the UI picks up fresh data.
_scan_state = _get_scan_state()
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

# ── Sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.markdown(ui.sidebar_header_html(), unsafe_allow_html=True)
st.sidebar.markdown("---")

st.sidebar.markdown("**Ticker Lookup (Local App Only)**")
custom_ticker_raw = st.sidebar.text_input(
    "Ticker symbol (e.g. PLTR, ARM, TSMC)",
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

_confirmed = st.session_state.get("_confirmed_custom_ticker", "")
using_custom_ticker = bool(_confirmed)

if using_custom_ticker:
    selected_category = "Custom Ticker"
    selected_asset = _confirmed
    ticker = _confirmed
else:
    categories = list(TRACKED_ASSETS.keys())
    default_cat_idx = categories.index(DEFAULT_CATEGORY) if DEFAULT_CATEGORY in categories else 0
    selected_category = (
        st.sidebar.selectbox("Category", categories, index=default_cat_idx)
        or categories[0]
    )

    asset_names = list(TRACKED_ASSETS[selected_category].keys())
    if not asset_names:
        st.error(f"No assets configured for category: {selected_category}")
        st.stop()
    selected_asset = st.sidebar.selectbox("Asset", asset_names) or asset_names[0]
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
st.sidebar.caption(f"Ticker: `{ticker}`")
st.sidebar.caption(f"Prices refresh: every {PRICE_CACHE_TTL}s")
st.sidebar.caption(f"News refresh: every {NEWS_CACHE_TTL}s")
st.sidebar.caption(f"Sentiment engine: {'VADER' if VADER_AVAILABLE else 'Keyword fallback'}")
st.sidebar.caption(f"Last refresh: {dt.datetime.now().strftime('%H:%M:%S')}")

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

_stale = is_data_stale(_summary)
if _stale:
    st.info("Data is stale. Refresh recommended.")

    if st.button("Refresh now"):
        st.session_state["_scan_refresh_epoch"] = st.session_state.get("_scan_refresh_epoch", 0) + 1
        st.session_state["_stale_refresh_triggered"] = True
        st.rerun()
  
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


# SECTION 1 — Signal card (snapshot)
ui.render_signal_card(snap, selected_category, selected_asset, chg_1d, is_significant)

# SECTION 2 — Why it matters (snapshot)
ui.render_why_box(snap)

# SECTION 3 — Metric cards + momentum row (snapshot)
st.markdown("---")
ui.render_snapshot_metrics(snap, chg_1d)

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
with st.expander("Price Chart & Live Analysis", expanded=False):
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
            try:
                history = cached_history(ticker)
            except DataFetchError as _price_exc:
                log.warning("Price fetch failed for %s: %s", ticker, _price_exc)
                history = pd.DataFrame()
            if history.empty:
                st.error(
                    f"Could not load price data for **{selected_asset}** (`{ticker}`). "
                    "Yahoo Finance may be temporarily unreachable. Try refreshing."
                )
            else:
                live_metrics  = compute_price_metrics(history)
                live_momentum = compute_momentum_metrics(history)

                _live_articles: list[dict] = cached_news() if _news_loaded else []
                live_news = correlate_news(
                    selected_asset,
                    _live_articles,
                    keywords=_custom_keywords,
                )

                market_ctx = None
                if (
                    run_context
                    and selected_category in TRACKED_ASSETS
                    and live_metrics.get("change_1d") is not None
                ):
                    with st.spinner("Analysing market context (peers + benchmark) ..."):
                        try:
                            market_ctx = analyse_market_context(
                                selected_asset, selected_category, live_metrics["change_1d"]
                            )
                        except Exception as _ctx_exc:
                            st.warning(
                                f"Market context analysis failed: {_ctx_exc}",
                                icon="warning",
                            )

                live_signal = compute_signal_score(
                    live_metrics, live_momentum, live_news, market_ctx,
                    category=selected_category,
                )
                live_explanation = build_explanation(
                    selected_asset, live_metrics, live_news, market_ctx,
                    live_momentum, live_signal,
                )

                ui.render_live_analysis(
                    history, selected_asset, live_signal, live_explanation,
                    snap, is_significant,
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
