"""
dashboard.py — PulseEngine web demo (restricted).

Restricted surface deployed to Streamlit Community Cloud.
Stateless: no file I/O, no persistent storage, no local model inference.

Features available:
  - All 24 tracked assets
  - Live signal score and explanation
  - Price chart and metrics
  - News sentiment feed
  - Market heatmap (computed live per session)

Locked features (local app only):
  - Arbitrary ticker lookup
  - Backtesting and historical snapshots
  - Export to CSV / PDF
  - FinBERT local model
  - Custom RSS feeds
  - Offline mode
  - Background scan daemon

Run with:  streamlit run pulseengine/web/dashboard.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import datetime as dt
import html as _html
import logging
from urllib.parse import urlparse

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pulseengine.core import (
    TRACKED_ASSETS,
    DASHBOARD_TITLE,
    DASHBOARD_ICON,
    DASHBOARD_LAYOUT,
    DEFAULT_CATEGORY,
    PRICE_CHANGE_THRESHOLD,
    RELEVANCE_HIGH,
    RELEVANCE_MEDIUM,
    VADER_AVAILABLE,
    correlate_news,
    get_display_clusters,
    compute_price_metrics,
    compute_momentum_metrics,
    compute_signal_score,
    build_explanation,
    fetch_news_articles,
    fetch_price_history,
    DataFetchError,
)
from pulseengine.core.config import (
    CHART_HEIGHT,
    NEWS_CACHE_TTL,
    PRICE_CACHE_TTL,
)

log = logging.getLogger(__name__)

# ── Page configuration ─────────────────────────────────────────────────────────

st.set_page_config(
    page_title=f"{DASHBOARD_TITLE} — Demo",
    page_icon=DASHBOARD_ICON,
    layout=DASHBOARD_LAYOUT,  # type: ignore[arg-type]
)

# ── CSS (same Retro Financial Broadsheet theme) ────────────────────────────────

from pulseengine.local.styles import load_css
load_css()

# ── Cached data loaders ────────────────────────────────────────────────────────

@st.cache_data(ttl=NEWS_CACHE_TTL, show_spinner="Fetching news feeds ...")
def _cached_news() -> list[dict]:
    return fetch_news_articles()


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner="Fetching price history ...")
def _cached_history(symbol: str) -> pd.DataFrame:
    result = fetch_price_history(symbol)
    return result if result is not None else pd.DataFrame()


# ── Article renderer ──────────────────────────────────────────────────────────

def _render_article(item: dict) -> None:
    sent       = item.get("sentiment", {}).get("compound", 0.0)
    sent_word  = "Positive" if sent > 0.05 else "Negative" if sent < -0.05 else "Neutral"
    sent_color = "#7db888" if sent > 0.05 else "#c08080" if sent < -0.05 else "#635a48"

    rel = item.get("relevance_score", 0)
    rel_html = (
        '<span class="rel-high">HIGH</span>' if rel >= RELEVANCE_HIGH
        else '<span class="rel-med">MED</span>' if rel >= RELEVANCE_MEDIUM
        else '<span class="rel-low">LOW</span>'
    )

    src_w = item.get("source_weight", 1.0)
    pub   = ""
    if item.get("published"):
        pub = item["published"].strftime("%b %d, %H:%M")

    raw_summary = item.get("summary", "") if isinstance(item.get("summary"), str) else ""
    summary     = _html.escape(raw_summary[:220])
    if len(raw_summary) > 220:
        summary += " ..."

    raw_link = item.get("link", "")
    try:
        _parsed = urlparse(raw_link)
        safe_link = _html.escape(raw_link, quote=True) if _parsed.scheme in ("http", "https") else "#"
    except ValueError:
        safe_link = "#"

    safe_title  = _html.escape(item.get("title", ""))
    safe_source = _html.escape(item.get("source", ""))

    st.markdown(
        f'<div class="news-row">'
        f'<strong style="color:#e4d9c4;font-family:var(--font-display)">{safe_title}</strong><br>'
        f'<span class="news-meta">'
        f'{safe_source} (weight {src_w:.2f}) &middot; {pub} &middot; '
        f'<span style="color:{sent_color}">{sent_word} ({sent:+.2f})</span>'
        f' &middot; Relevance: {rel_html}'
        f'</span>'
        f'<br><span style="color:#9e9078;font-size:0.87rem;font-style:italic">{summary}</span>'
        f'<br><a href="{safe_link}" target="_blank" '
        f'style="color:#8a7040;font-size:0.82rem">Read full article →</a>'
        f'</div>',
        unsafe_allow_html=True,
    )


# ── Signal CSS map ─────────────────────────────────────────────────────────────

_SIGNAL_CLASS_MAP: dict[str, str] = {
    "Strong Bullish":   "signal-strong-bull",
    "Bullish":          "signal-bull",
    "Slightly Bullish": "signal-slight-bull",
    "Neutral":          "signal-neutral",
    "Slightly Bearish": "signal-slight-bear",
    "Bearish":          "signal-bear",
    "Strong Bearish":   "signal-strong-bear",
}

# ── Sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.markdown("## PulseEngine")
st.sidebar.caption("Market Intelligence Platform — Web Demo")
st.sidebar.markdown("---")

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
st.sidebar.caption(f"Ticker: `{ticker}`")
st.sidebar.caption(f"Sentiment engine: {'VADER' if VADER_AVAILABLE else 'Keyword fallback'}")
st.sidebar.caption(f"Last refresh: {dt.datetime.now().strftime('%H:%M:%S')}")

if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()
    st.rerun()

st.sidebar.markdown("---")

with st.sidebar.expander("Signal Interpretation", expanded=False):
    st.markdown(
        """
        **+6 to +10** — Strong Bullish

        **+2 to +6** — Bullish

        **-2 to +2** — Neutral

        **-6 to -2** — Bearish

        **-10 to -6** — Strong Bearish
        """
    )
    st.caption("Scores are weighted composite signals, not raw price change.")

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Want the full experience?**\n\n"
    "The web demo shows live signals for the 24 tracked assets. "
    "The local app adds arbitrary ticker lookup, backtesting, historical snapshots, "
    "and offline mode. It's free, MIT-licensed, and runs entirely on your machine."
)
st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Data sources (free, public):**  \n"
    "Yahoo Finance · Reuters · CNBC  \n"
    "BBC · CoinDesk · Google News  \n"
    "NPR · MarketWatch · Al Jazeera"
)

# ── Main panel ─────────────────────────────────────────────────────────────────

st.markdown(f"# {selected_asset}")
st.caption(f"{selected_category}  ·  `{ticker}`  ·  last 30 days  ·  Web Demo")

_live_loaded = st.session_state.get("_live_for") == ticker
_news_loaded = st.session_state.get("_news_for") == ticker

# ── SECTION 1 — Live signal (computed fresh, no disk) ─────────────────────────

if not _live_loaded:
    st.markdown("### Signal")
    st.info(
        "Live analysis is not fetched on startup. "
        "Click below to load 30-day OHLCV from Yahoo Finance and compute the signal."
    )
    if st.button("Load live signal", key="_live_btn"):
        st.session_state["_live_for"] = ticker
        st.rerun()
else:
    with st.spinner("Computing live signal ..."):
        try:
            history = _cached_history(ticker)
        except DataFetchError as _exc:
            log.warning("Price fetch failed for %s: %s", ticker, _exc)
            history = pd.DataFrame()

    if history.empty:
        st.error(
            f"Could not load price data for **{selected_asset}** (`{ticker}`). "
            "Yahoo Finance may be temporarily unreachable. Try refreshing."
        )
    else:
        live_metrics  = compute_price_metrics(history)
        live_momentum = compute_momentum_metrics(history)

        _articles: list[dict] = _cached_news() if _news_loaded else []
        live_news = correlate_news(selected_asset, _articles)

        live_signal = compute_signal_score(
            live_metrics, live_momentum, live_news, None,
            category=selected_category,
        )
        live_explanation = build_explanation(
            selected_asset, live_metrics, live_news, None,
            live_momentum, live_signal,
        )

        sig_score = float(live_signal.get("score") or 0.0)
        sig_label = live_signal.get("label") or "Neutral"
        conf      = live_explanation.get("confidence") or "low"
        conf_cls  = {"high": "conf-high", "medium": "conf-medium"}.get(conf, "conf-low")
        sig_css   = _SIGNAL_CLASS_MAP.get(sig_label, "signal-neutral")

        chg_1d = live_metrics.get("change_1d")
        is_significant = chg_1d is not None and abs(chg_1d) >= PRICE_CHANGE_THRESHOLD

        # Signal card
        sig_col, _spacer = st.columns([2, 3])
        with sig_col:
            st.markdown(
                f'<div class="signal-card {sig_css}">'
                f'<div class="signal-label-text">{sig_label}'
                f'<span class="confidence-badge {conf_cls}">Confidence: {conf.upper()}</span>'
                f'</div>'
                f'<div class="signal-score-text">Score: {sig_score:+.1f} / 10'
                f'&nbsp;&nbsp;&middot;&nbsp;&nbsp;'
                f'<span style="font-size:0.9rem;opacity:0.7">{selected_category}</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if is_significant and chg_1d is not None:
            verb = "surged" if chg_1d > 0 else "dropped"
            st.warning(f"Significant move: {selected_asset} {verb} {abs(chg_1d):.2f}% in 24 hours.")

        # Why it matters
        verdict = live_explanation.get("verdict", "")
        if verdict:
            st.markdown(
                f'<div class="why-box">'
                f'<div class="why-label">Why it matters</div>'
                f'{_html.escape(verdict)}'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Metric cards
        st.markdown("---")
        price = live_metrics.get("latest_price") or 0
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        with mc1:
            st.metric("Price", f"${price:,.2f}",
                      delta=(f"{chg_1d:+.2f}% (24h)" if chg_1d is not None else None))
        with mc2:
            v7 = live_metrics.get("change_7d")
            st.metric("7-Day", f"{v7:+.2f}%" if v7 is not None else "N/A")
        with mc3:
            v30 = live_metrics.get("change_30d")
            st.metric("30-Day", f"{v30:+.2f}%" if v30 is not None else "N/A")
        with mc4:
            vol = live_metrics.get("volatility")
            st.metric("Volatility", f"{vol:.2f}%" if vol is not None else "N/A")
        with mc5:
            trend = live_metrics.get("trend") or "sideways"
            st.metric("Trend", trend.title())

        m1, m2, m3, m4 = st.columns(4)
        rsi = float(live_momentum.get("rsi") or 50.0)
        roc = float(live_momentum.get("roc_10d") or 0.0)
        with m1:
            rsi_delta = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else None
            st.metric("RSI (14-day)", f"{rsi:.1f}", delta=rsi_delta)
        with m2:
            st.metric("10-day ROC", f"{roc:+.2f}%")
        with m3:
            ts = live_momentum.get("trend_strength")
            st.metric("Trend Strength", f"{ts:+.2f}%" if ts is not None else "N/A")
        with m4:
            ma = live_momentum.get("momentum_accel")
            st.metric("Momentum Accel", f"{ma:+.2f}%" if ma is not None else "N/A")

        # Price chart
        st.markdown("---")
        close_col = history["Close"]
        if isinstance(close_col, pd.DataFrame):
            close_col = close_col.iloc[:, 0]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=history.index, y=close_col,
            mode="lines",
            line=dict(color="#c4a35a", width=2.0),
            fill="tozeroy",
            fillcolor="rgba(196,163,90,0.06)",
            name="Close",
            hovertemplate="$%{y:,.4f}<br>%{x|%b %d}<extra></extra>",
        ))
        if len(close_col) >= 7:
            fig.add_trace(go.Scatter(
                x=history.index, y=close_col.rolling(7).mean(),
                mode="lines",
                line=dict(color="#8a7040", width=1.4, dash="dash"),
                name="7d MA",
                hovertemplate="MA7: $%{y:,.4f}<extra></extra>",
            ))
        if len(close_col) >= 20:
            fig.add_trace(go.Scatter(
                x=history.index, y=close_col.rolling(20).mean(),
                mode="lines",
                line=dict(color="#5a5040", width=1.2, dash="dot"),
                name="20d MA",
                hovertemplate="MA20: $%{y:,.4f}<extra></extra>",
            ))
        fig.update_layout(
            height=CHART_HEIGHT,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, color="#635a48", tickformat="%b %d"),
            yaxis=dict(showgrid=True, gridcolor="rgba(82,72,64,0.2)",
                       color="#635a48", tickprefix="$"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02,
                        xanchor="right", x=1, font=dict(size=11, color="#9e9078")),
            hovermode="x unified",
            font=dict(family="Georgia, 'Times New Roman', serif"),
        )
        st.markdown("### Price History (30 days)")
        st.plotly_chart(fig, config={"responsive": True})

        # Locked features prompt
        st.markdown("---")
        st.info(
            "**Local app features not available in the web demo:**  \n"
            "Arbitrary ticker lookup · Backtesting · Historical snapshots · "
            "Export to CSV/PDF · FinBERT local model · Offline mode  \n\n"
            "All features are free. Download and run locally — no accounts, no cloud.",
            icon="ℹ️",
        )

# ── SECTION 2 — Related News (deferred) ───────────────────────────────────────

st.markdown("---")
if not _news_loaded:
    st.markdown("### Related News")
    if st.button("Load news feed", key="_news_btn"):
        st.session_state["_news_for"] = ticker
        st.rerun()
    st.caption("News is not fetched on startup. Click above to load from 12 RSS feeds.")
else:
    articles   = _cached_news()
    news       = correlate_news(selected_asset, articles)
    disp_clust = get_display_clusters(news, max_clusters=2)
    clusters   = disp_clust["clusters"]
    suppressed = disp_clust["suppressed_count"]

    if not news:
        st.markdown("### Related News")
        st.info("No recent articles matched this asset.")
    elif clusters:
        cluster_count = len(clusters)
        st.markdown(
            f"## Related News — Top {cluster_count} Cluster{'s' if cluster_count > 1 else ''}"
            + (f" ({suppressed} low-relevance article(s) suppressed)" if suppressed > 0 else "")
        )
        for cluster in clusters:
            sent_c = cluster["avg_sentiment"]
            sent_color = "#7db888" if sent_c > 0.05 else "#c08080" if sent_c < -0.05 else "#635a48"
            st.markdown(
                f'<div class="cluster-card">'
                f'<div class="cluster-header-row">'
                f'<span class="cluster-title">{cluster["label"]}</span>'
                f'<span class="cluster-meta">'
                f'{cluster["count"]} article{"s" if cluster["count"] != 1 else ""}'
                f' &middot; sentiment: '
                f'<span style="color:{sent_color}">{cluster["sentiment_summary"]}</span>'
                f'</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            for art in cluster["articles"][:3]:
                _render_article(art)

        shown_set = {id(a) for c in clusters for a in c["articles"][:3]}
        remaining = [a for a in news if id(a) not in shown_set]
        if remaining:
            with st.expander(f"More articles ({len(remaining)} remaining)"):
                for art in remaining[:10]:
                    _render_article(art)
    else:
        st.markdown(f"## Related News ({len(news)} articles)")
        for art in news[:10]:
            _render_article(art)


# ── Footer ─────────────────────────────────────────────────────────────────────

st.markdown("---")
st.caption(
    "PulseEngine Web Demo  ·  "
    "Yahoo Finance (prices) + Public RSS (news) + VADER (sentiment)  ·  "
    "No data is stored. Ever.  ·  "
    "This is not financial advice."
)
