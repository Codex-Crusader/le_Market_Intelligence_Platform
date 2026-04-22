"""
components.py — Reusable UI rendering functions for the PulseEngine local dashboard.

Each function takes pre-computed data as arguments and issues Streamlit calls.
No heavy computation, no network calls, no caching here — that belongs in
pulseengine.core / pulseengine.local.scan / pulseengine.local.data respectively.
"""

from __future__ import annotations

import base64
import datetime as dt
import html as _html
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pulseengine.core import DASHBOARD_ICON, RELEVANCE_HIGH, RELEVANCE_MEDIUM, TRACKED_ASSETS
from pulseengine.core.config import CHART_HEIGHT, SCAN_INTERVAL_MINUTES

# ── Optional dependencies ──────────────────────────────────────────────────────

try:
    from pulseengine.core import evaluate_signal_accuracy, get_signal_streak
    _BACKTEST_AVAILABLE = True
except ImportError:
    _BACKTEST_AVAILABLE = False
    def evaluate_signal_accuracy(*_a, **_kw): return {}   # noqa: E731
    def get_signal_streak(*_a, **_kw): return {"type": "none", "length": 0}  # noqa: E731

try:
    from pulseengine.core import get_historical_features
    _STORAGE_AVAILABLE = True
except ImportError:
    _STORAGE_AVAILABLE = False
    def get_historical_features(*_a, **_kw): return {}    # noqa: E731

# ── Internal constants ─────────────────────────────────────────────────────────

_SIGNAL_CLASS_MAP: dict[str, str] = {
    "Strong Bullish":   "signal-strong-bull",
    "Bullish":          "signal-bull",
    "Slightly Bullish": "signal-slight-bull",
    "Neutral":          "signal-neutral",
    "Slightly Bearish": "signal-slight-bear",
    "Bearish":          "signal-bear",
    "Strong Bearish":   "signal-strong-bear",
}

_WARN_FACTOR_TYPES = {"rsi_overbought", "rsi_oversold", "sentiment_diverged", "volatility"}


# ── Sidebar helpers ────────────────────────────────────────────────────────────

def _build_logo_html() -> str:
    # File lives at pulseengine/local/components.py — project root is 3 levels up
    logo_path = Path(__file__).resolve().parent.parent.parent / "assets" / "logo" / "pulseengine_logo.png"
    if logo_path.exists():
        data = base64.b64encode(logo_path.read_bytes()).decode()
        return (
            f'<img src="data:image/png;base64,{data}" '
            f'style="width:100%;max-width:190px;display:block;'
            f'margin:0 auto 4px auto;opacity:0.93;" />'
        )
    return f"<span style='font-size:1.4rem'>{DASHBOARD_ICON}</span>"


# Logo HTML is static for the lifetime of the process — build it once at import
# time so the PNG is not read and base64-encoded on every Streamlit rerun.
_LOGO_HTML: str = _build_logo_html()


def sidebar_header_html() -> str:
    """Return the full sidebar header HTML (logo + subtitle)."""
    return f"""
    <div style="text-align:center;padding:10px 0 6px 0;">
      {_LOGO_HTML}
      <div style="
        font-family:'EB Garamond','Georgia',serif;
        font-size:0.66rem;
        font-weight:400;
        letter-spacing:0.22em;
        text-transform:uppercase;
        color:#8a7650;
        margin-top:4px;
      ">Market Intelligence Platform</div>
    </div>
    """


def _format_scan_label(scan_state: dict, summary: dict) -> tuple[str, str]:
    """Return (human-readable label, CSS colour) for the scan status line."""
    if scan_state["running"]:
        return "⏳ Scan running...", "#a07840"

    ts = summary.get("scan_time")
    if not ts:
        return "No scan data yet", "#635a48"

    try:
        last_dt = dt.datetime.fromisoformat(ts)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=dt.timezone.utc)
        age_sec = int((dt.datetime.now(dt.timezone.utc) - last_dt).total_seconds())
        age_min = max(age_sec // 60, 0)
    except (ValueError, TypeError):
        return "No scan data yet", "#635a48"

    if age_min < 1:
        ago = "just now"
    elif age_min < 60:
        ago = f"{age_min} min ago"
    else:
        h, m = divmod(age_min, 60)
        ago = f"{h}h {m}m ago" if m else f"{h}h ago"

    next_min = max(SCAN_INTERVAL_MINUTES - age_min, 0)
    label = f"✅ Last scanned {ago}  ·  next scan in ~{next_min} min"
    color = "#8a7040" if age_min < SCAN_INTERVAL_MINUTES else "#635a48"
    return label, color


def render_scan_status_sidebar(scan_state: dict, summary: dict) -> None:
    """Render the scan age label plus assets-done / error captions in the sidebar."""
    label, color = _format_scan_label(scan_state, summary)
    st.sidebar.markdown(
        f'<span style="font-size:0.80rem;color:{color};font-style:italic">{label}</span>',
        unsafe_allow_html=True,
    )
    if scan_state.get("assets_done"):
        st.sidebar.caption(f"{scan_state['assets_done']} assets in last scan")
    error_count = scan_state.get("errors_count", 0) or len(summary.get("errors", []))
    if error_count:
        st.sidebar.caption(f"{error_count} asset(s) reported scan errors")
    if scan_state.get("error"):
        st.sidebar.caption(f"Scan error: {scan_state['error'][:80]}")


def render_signal_legend_sidebar() -> None:
    """Render a compact signal interpretation legend in the sidebar."""
    with st.sidebar.expander("Signal Interpretation", expanded=False):
        st.markdown(
            """
            **+6 to +10**
            Strong Bullish

            **+2 to +6**
            Bullish

            **-2 to +2**
            Neutral

            **-6 to -2**
            Bearish

            **-10 to -6**
            Strong Bearish
            """
        )
        st.caption("Scores are weighted composite signals, not raw price change.")


def render_mover_rows(gainers: list[dict], losers: list[dict], summary_date: str) -> None:
    """Render the Top Movers gainers/losers lists in the sidebar."""
    if not gainers and not losers:
        st.caption("No scan data yet — run a full scan to see top movers.")
        return

    def _mover_html(items: list[dict], color: str) -> str:
        return "".join(
            f'<div class="mover-row">'
            f'<span style="color:#9e9078">{m["name"]}</span>'
            f'<span style="color:{color};font-weight:600">{m["chg"]:+.2f}%</span>'
            f'</div>'
            for m in items
        )

    if gainers:
        st.markdown(
            '<div style="margin-bottom:6px;font-size:0.72rem;color:#8a7040;'
            'font-weight:600;letter-spacing:0.10em;text-transform:uppercase;font-style:italic">Gainers</div>'
            + _mover_html(gainers, "#7db888"),
            unsafe_allow_html=True,
        )
    if losers:
        st.markdown(
            '<div style="margin-top:10px;margin-bottom:6px;font-size:0.72rem;'
            'color:#7a3a3a;font-weight:600;letter-spacing:0.10em;text-transform:uppercase;font-style:italic">Losers</div>'
            + _mover_html(losers, "#c08080"),
            unsafe_allow_html=True,
        )
    if summary_date:
        st.caption(f"From scan: {summary_date}")


# ── Main panel banners ─────────────────────────────────────────────────────────

def render_data_status_banner(scan_state: dict, stale: bool, summary: dict) -> None:
    """Show scan-running info, stale-data warning, and last-updated caption."""
    if scan_state["running"]:
        st.info("Updating market data in background — snapshot data shown below.", icon="🔄")
    elif stale:
        st.warning(
            "Market data may be outdated. A background refresh has been triggered. "
            "Use **Refresh Data** in the sidebar to reload immediately.",
            icon="⚠️",
        )

    scan_time = summary.get("scan_time", "")
    if scan_time:
        try:
            last_dt = dt.datetime.fromisoformat(scan_time)
            st.caption(f"Market data last updated: {last_dt.strftime('%Y-%m-%d %H:%M')}")
        except (ValueError, TypeError):
            pass


# ── Section 1 — Signal card ────────────────────────────────────────────────────

def render_signal_card(
    snap: dict,
    selected_category: str,
    selected_asset: str,
    chg_1d: float | None,
    is_significant: bool,
) -> None:
    """Render the signal card (and significant-move warning if applicable)."""
    sig_score  = float(snap.get("signal_score") or 0.0)
    sig_label  = snap.get("signal_label") or "Neutral"
    low_news_conf = bool(snap.get("low_news_confidence", False))
    news_count = int(snap.get("news_article_count", 0) or 0)
    conf       = snap.get("confidence") or "low"
    conf_class = {"high": "conf-high", "medium": "conf-medium"}.get(conf, "conf-low")
    conf_label = conf.upper()
    sig_css    = _SIGNAL_CLASS_MAP.get(sig_label, "signal-neutral")

    sig_col, _spacer = st.columns([2, 3])
    with sig_col:
        if snap:
            st.markdown(
                f'<div class="signal-card {sig_css}">'
                f'<div class="signal-label-text">{sig_label}'
                f'<span class="confidence-badge {conf_class}">Confidence: {conf_label}</span>'
                f'</div>'
                f'<div class="signal-score-text">Score: {sig_score:+.1f} / 10'
                f'&nbsp;&nbsp;&middot;&nbsp;&nbsp;'
                f'<span style="font-size:0.9rem;opacity:0.7">{selected_category}</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info("No snapshot data yet — run a full scan from the sidebar.")

    if low_news_conf:
        st.warning(
            "⚠️ Low news coverage — this signal is based primarily on price data. "
            "Sentiment component has low confidence.",
            icon="⚠️",
        )
        st.caption(f"Matched relevant articles: {news_count}")

    if is_significant and chg_1d is not None:
        verb = "surged" if chg_1d > 0 else "dropped"
        st.warning(
            f"Significant move: {selected_asset} {verb} {abs(chg_1d):.2f}% in 24 hours."
        )


# ── Section 2 — Why-it-matters box ────────────────────────────────────────────

def render_why_box(snap: dict) -> None:
    """Render the 'Why it matters' verdict box if the snapshot has one."""
    verdict = snap.get("verdict", "")
    if verdict:
        st.markdown(
            f'<div class="why-box">'
            f'<div class="why-label">Why it matters</div>'
            f'{_html.escape(verdict)}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Section 3 — Snapshot metric cards ─────────────────────────────────────────

def render_snapshot_metrics(snap: dict, chg_1d: float | None) -> None:
    """Render the 5-column price metrics and 4-column momentum row from the snapshot."""
    if not snap:
        st.info("Run a full scan to populate metric data.")
        return

    price = snap.get("price") or 0
    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    with mc1:
        st.metric(
            "Price",
            f"${price:,.2f}",
            delta=(f"{chg_1d:+.2f}% (24h)" if chg_1d is not None else None),
        )
    with mc2:
        v7 = snap.get("change_7d")
        st.metric("7-Day", f"{v7:+.2f}%" if v7 is not None else "N/A")
    with mc3:
        v30 = snap.get("change_30d")
        st.metric("30-Day", f"{v30:+.2f}%" if v30 is not None else "N/A")
    with mc4:
        vol = snap.get("volatility")
        st.metric("Volatility", f"{vol:.2f}%" if vol is not None else "N/A")
    with mc5:
        trend = snap.get("trend") or "sideways"
        st.metric("Trend", trend.title())

    m1, m2, m3, m4 = st.columns(4)
    rsi = float(snap.get("rsi") or 50.0)
    roc = float(snap.get("roc_10d") or 0.0)
    with m1:
        rsi_delta = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else None
        st.metric("RSI (14-day)", f"{rsi:.1f}", delta=rsi_delta)
    with m2:
        st.metric("10-day ROC", f"{roc:+.2f}%")
    with m3:
        ts = snap.get("trend_strength")
        st.metric("Trend Strength", f"{ts:+.2f}%" if ts is not None else "N/A",
                  help="MA7 vs MA30 divergence")
    with m4:
        ma = snap.get("momentum_accel")
        st.metric("Momentum Accel", f"{ma:+.2f}%" if ma is not None else "N/A",
                  help="Recent 5d ROC minus prior 5d ROC")


# ── Section 4 — News ──────────────────────────────────────────────────────────

def render_article(item: dict) -> None:
    """Render a single news article as a styled card."""
    sent       = item.get("sentiment", {}).get("compound", 0.0)
    sent_word  = "Positive" if sent > 0.05 else "Negative" if sent < -0.05 else "Neutral"
    sent_color = "#7db888" if sent > 0.05 else "#c08080" if sent < -0.05 else "#635a48"

    rel = item.get("relevance_score", 0)
    rel_html = (
        '<span class="rel-high">HIGH</span>'  if rel >= RELEVANCE_HIGH
        else '<span class="rel-med">MED</span>'  if rel >= RELEVANCE_MEDIUM
        else '<span class="rel-low">LOW</span>'
    )

    src_w = item.get("source_weight", 1.0)
    pub   = ""
    if item.get("published"):
        pub = item["published"].strftime("%b %d, %H:%M")

    events_html = ""
    if item.get("events_detected"):
        tags = " · ".join(
            f'{e.get("icon", "")} {e.get("label", "")}'.strip()
            for e in item["events_detected"]
        )
        events_html = f'<br><span style="font-size:0.80rem;color:#635a48">{tags}</span>'

    raw_summary = item.get("summary", "") if isinstance(item.get("summary"), str) else ""
    summary     = _html.escape(raw_summary[:220])
    if len(raw_summary) > 220:
        summary += " ..."

    raw_link = item.get("link", "")
    try:
        _parsed_link = urlparse(raw_link)
        safe_link = _html.escape(raw_link, quote=True) if _parsed_link.scheme in ("http", "https") else "#"
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
        f'{events_html}'
        f'<br><span style="color:#9e9078;font-size:0.87rem;font-style:italic">{summary}</span>'
        f'<br><a href="{safe_link}" target="_blank" '
        f'style="color:#8a7040;font-size:0.82rem">Read full article →</a>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_news_section(
    clusters_data: list[dict],
    suppressed: int,
    total_news: int,
    news: list[dict],
) -> None:
    """Render clustered or flat news results (handles all three states)."""
    if not news:
        st.markdown("## Related News")
        st.info("No recent articles matched this asset. Try a different one.")
        return

    if clusters_data:
        cluster_count = len(clusters_data)
        st.markdown(
            f"## Related News — Top {cluster_count} Cluster{'s' if cluster_count > 1 else ''}"
            + (f" ({suppressed} low-relevance article(s) suppressed)" if suppressed > 0 else "")
        )

        for cluster in clusters_data:
            sent_color_c = (
                "#7db888" if cluster["avg_sentiment"] > 0.05
                else "#c08080" if cluster["avg_sentiment"] < -0.05
                else "#635a48"
            )
            st.markdown(
                f'<div class="cluster-card">'
                f'<div class="cluster-header-row">'
                f'<span class="cluster-title">{cluster["label"]}</span>'
                f'<span class="cluster-meta">'
                f'{cluster["count"]} article{"s" if cluster["count"] != 1 else ""}'
                f' &middot; sentiment: '
                f'<span style="color:{sent_color_c}">{cluster["sentiment_summary"]}</span>'
                f'</span>'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
            for art in cluster["articles"][:3]:
                render_article(art)

        shown_set = {id(a) for c in clusters_data for a in c["articles"][:3]}
        remaining = [a for a in news if id(a) not in shown_set]
        if remaining:
            with st.expander(f"More articles ({len(remaining)} remaining)"):
                for art in remaining[:10]:
                    render_article(art)
    else:
        st.markdown(f"## Related News ({total_news} articles)")
        for article in news[:10]:
            render_article(article)


# ── Section 5 — Live analysis (price chart + signal breakdown) ────────────────

def _render_primary_driver(primary_driver: dict) -> None:
    st.markdown(
        f'<div class="driver-box">'
        f'<div class="driver-label">Primary driver</div>'
        f'<strong>{primary_driver["label"]}</strong>'
        + (f' — {primary_driver["detail"]}' if primary_driver.get("detail") else "")
            + '</div>',
        unsafe_allow_html=True,
    )


def _render_factor_pills(live_factors: list[dict]) -> None:
    pills_html = "".join(
        f'<span class="factor-pill'
        f'{" factor-pill-warn" if f["type"] in _WARN_FACTOR_TYPES else ""}">'
        f'{f["label"]}</span>'
        for f in live_factors
    )
    st.markdown(f"**Contributing factors:** {pills_html}", unsafe_allow_html=True)


def _render_contradictions(contradictions: list[dict]) -> None:
    with st.expander(f"Risks and contradictions ({len(contradictions)})"):
        for c in contradictions:
            st.markdown(
                f'<div class="contra-box">'
                f'<strong>{c["type"].replace("_", " ").title()}:</strong> '
                f'{c["description"]}'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_confidence_reasoning(conf_info: dict) -> None:
    with st.expander("Confidence reasoning"):
        if conf_info.get("increases"):
            st.markdown("**Increases confidence:**")
            for r in conf_info["increases"]:
                st.markdown(f"- {r}")
        if conf_info.get("decreases"):
            st.markdown("**Decreases confidence:**")
            for r in conf_info["decreases"]:
                st.markdown(f"- {r}")
        st.caption(f"Confidence score: {conf_info.get('score', 0)} / 12")


def _render_price_chart(history: pd.DataFrame) -> None:
    """Render the 30-day close price chart with optional MA overlays."""
    st.markdown("### Price History")
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
        yaxis=dict(
            showgrid=True,
            gridcolor="rgba(82,72,64,0.2)",
            color="#635a48",
            tickprefix="$",
        ),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1, font=dict(size=11, color="#9e9078"),
        ),
        hovermode="x unified",
        font=dict(family="Georgia, 'Times New Roman', serif"),
    )
    st.plotly_chart(fig, config={"responsive": True})


def _render_volume_chart(history: pd.DataFrame) -> None:
    with st.expander("Volume chart"):
        if "Volume" not in history.columns:
            st.info("Volume data not available.")
            return
        vol_col = history["Volume"]
        if isinstance(vol_col, pd.DataFrame):
            vol_col = vol_col.iloc[:, 0]
        vfig = go.Figure(go.Bar(
            x=history.index, y=vol_col,
            marker=dict(color="rgba(196,163,90,0.25)"),
            hovertemplate="%{y:,.0f}<extra></extra>",
        ))
        vfig.update_layout(
            height=200,
            margin=dict(l=0, r=0, t=0, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, color="#635a48"),
            yaxis=dict(showgrid=False, color="#635a48"),
            font=dict(family="Georgia, 'Times New Roman', serif"),
        )
        st.plotly_chart(vfig, config={"responsive": True})


def _render_signal_components(live_signal: dict) -> None:
    with st.expander("Signal component breakdown"):
        comps = live_signal.get("components", {})
        if not comps:
            st.info("No component data available.")
            return
        comp_names  = list(comps.keys())
        comp_values = [comps[k] for k in comp_names]
        colors      = ["#4a7a52" if v >= 0 else "#7a3a3a" for v in comp_values]

        max_abs = max((abs(v) for v in comp_values), default=1.0)
        y_range = max(round(max_abs * 1.30 + 0.2, 1), 1.5)

        cfig = go.Figure(go.Bar(
            x=comp_names,
            y=comp_values,
            marker=dict(color=colors),
            text=[f"{v:+.2f}" for v in comp_values],
            textposition="outside",
        ))
        cfig.update_layout(
            height=220,
            margin=dict(l=0, r=0, t=10, b=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(color="#635a48"),
            yaxis=dict(
                color="#635a48",
                showgrid=True,
                gridcolor="rgba(82,72,64,0.2)",
                range=[-y_range, y_range],
            ),
            font=dict(family="Georgia, 'Times New Roman', serif", color="#9e9078"),
        )
        cfig.add_hline(y=0, line_color="#524840", line_width=1)
        st.plotly_chart(cfig, config={"responsive": True})
        if live_signal.get("category"):
            st.caption(
                f"Per-class weights applied for {live_signal['category']}. "
                "Weighted values shown. Each component contributes to the -10 to +10 signal."
            )
        else:
            st.caption("Each component contributes to the -10 to +10 composite signal score.")


def _render_backtest_section(selected_asset: str) -> None:
    """Render the backtest expander (no-op when backtest module is unavailable)."""
    if not _BACKTEST_AVAILABLE:
        return

    bt = evaluate_signal_accuracy(selected_asset)
    if bt["num_evaluated"] == 0:
        with st.expander("Signal Backtest (no history yet)"):
            st.info(
                bt["message"] + "\n\n"
                "Snapshots are saved each time this app runs. "
                "Return after a few days to see backtest results."
            )
        return

    st.markdown("### Signal Backtest")
    hit_rate = bt["hit_rate"]
    streak   = get_signal_streak(bt["details"])

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        pct = f"{hit_rate * 100:.1f}%" if hit_rate is not None else "N/A"
        st.metric("Directional Accuracy", pct)
    with c2:
        st.metric("Signals Evaluated", bt["num_evaluated"])
    with c3:
        avg_str = f"{bt['avg_signal_score']:+.2f}" if bt["avg_signal_score"] is not None else "N/A"
        st.metric("Avg Signal Score", avg_str)
    with c4:
        if streak["type"] != "none":
            st.metric("Current Streak", f"{streak['length']} {streak['type'].upper()}")

    st.caption(bt["message"])

    if bt.get("label_summaries"):
        with st.expander("Accuracy by signal label"):
            for s in bt["label_summaries"]:
                st.markdown(f"- {s}")

    bss = bt.get("by_signal_strength", {})
    if bss:
        with st.expander("Accuracy by signal strength"):
            for bucket in ("strong", "moderate", "weak"):
                if bucket in bss:
                    st.markdown(f"- {bss[bucket]['summary']}")

    if bt["details"]:
        with st.expander("Signal history (last 15)"):
            detail_rows = [
                {
                    "Date":      d["date"],
                    "Signal":    d["signal_label"],
                    "Score":     d["signal_score"],
                    "Predicted": d["predicted"],
                    "Actual":    f"{d['actual_change']:+.2f}% ({d['actual']})",
                    "Correct":   "Yes" if d["correct"] else "No",
                }
                for d in bt["details"][:15]
            ]
            bt_df     = pd.DataFrame(detail_rows)
            bt_styled = bt_df.style.map(
                lambda v: "color:#7db888" if v == "Yes" else "color:#c08080" if v == "No" else "",
                subset=["Correct"],
            )
            st.dataframe(bt_styled, width="stretch", hide_index=True)


def _render_historical_context(selected_asset: str, snap: dict) -> None:
    """Render the historical context expander (no-op when storage is unavailable)."""
    if not _STORAGE_AVAILABLE:
        return

    hist_feat = get_historical_features(selected_asset)
    if hist_feat.get("available", 0) < 2:
        return

    with st.expander("Historical context"):
        consistency = hist_feat.get("signal_consistency")
        persistence = hist_feat.get("trend_persistence", 0)
        t_vs_y      = hist_feat.get("today_vs_yesterday", {})

        hf_parts: list[str] = []
        if consistency is not None:
            hf_parts.append(
                f"Signal consistency over last {hist_feat['available']} snapshots: "
                f"**{consistency * 100:.0f}%** pointing same direction as today."
            )
        if persistence > 0:
            hf_parts.append(
                f"Trend **{snap.get('trend', 'unknown')}** has persisted "
                f"for **{persistence}** consecutive snapshot(s)."
            )
        if t_vs_y.get("signal_score"):
            d         = t_vs_y["signal_score"]
            direction = "higher" if d["change"] > 0 else "lower" if d["change"] < 0 else "unchanged"
            hf_parts.append(
                f"Signal score today ({d['today']:+.2f}) is **{direction}** "
                f"than yesterday ({d['yesterday']:+.2f}, change: {d['change']:+.2f})."
            )

        for part in hf_parts:
            st.markdown(part)

        st.caption(
            f"Based on {hist_feat['available']} stored snapshot(s). "
            "Snapshots accumulate as the app runs over multiple days."
        )


def render_live_analysis(
    history: pd.DataFrame,
    selected_asset: str,
    live_signal: dict,
    live_explanation: dict,
    snap: dict,
    is_significant: bool,
) -> None:
    """
    Render the full live-analysis block inside the Price Chart & Live Analysis
    expander: primary driver, factor pills, contradictions, confidence reasoning,
    price chart, volume chart, signal components, backtest, historical context,
    and full analysis text.
    """
    live_factors    = live_explanation.get("factors", [])
    event_factors   = [f for f in live_factors if f["type"] == "event"]
    context_factors = [
        f for f in live_factors
        if f["type"] in ("market_wide", "sector_wide", "asset_specific")
    ]
    primary_driver = next(iter(event_factors or context_factors or live_factors), None)

    if primary_driver:
        _render_primary_driver(primary_driver)

    if live_factors:
        _render_factor_pills(live_factors)

    contradictions = live_explanation.get("contradictions", [])
    if contradictions:
        _render_contradictions(contradictions)

    conf_info = live_explanation.get("confidence_info", {})
    if conf_info.get("increases") or conf_info.get("decreases"):
        _render_confidence_reasoning(conf_info)

    _render_price_chart(history)
    _render_volume_chart(history)
    _render_signal_components(live_signal)
    _render_backtest_section(selected_asset)
    _render_historical_context(selected_asset, snap)

    live_score = abs(live_signal.get("score") or 0)
    with st.expander("Full Analysis", expanded=is_significant or live_score >= 3.0):
        st.markdown(live_explanation["detail"])


# ── Section 13 — Market heatmap ───────────────────────────────────────────────

def render_heatmap(summary: dict, summary_date: str) -> None:
    """Render the Market Heatmap — 24h Changes plotly figure."""
    heatmap_data     = summary.get("heatmap", {})
    cats_for_heatmap = heatmap_data.get("categories", list(TRACKED_ASSETS.keys()))
    max_assets       = heatmap_data.get("max_assets", 1)
    z_matrix         = heatmap_data.get("z", [])
    text_matrix      = heatmap_data.get("text", [])

    hm_fig = go.Figure(go.Heatmap(
        z=z_matrix,
        x=[f"#{i+1}" for i in range(max_assets)],
        y=cats_for_heatmap,
        text=text_matrix,
        texttemplate="%{text}",
        colorscale=[
            [0.0, "#3d1010"],
            [0.2, "#7a3a3a"],
            [0.4, "#a06060"],
            [0.5, "#1a1510"],
            [0.6, "#4a6e50"],
            [0.8, "#4a7a52"],
            [1.0, "#5a9a62"],
        ],
        zmid=0, zmin=-5, zmax=5,
        showscale=True,
        colorbar=dict(
            title=dict(text="24h %", font=dict(color="#635a48", family="Georgia, serif")),
            tickfont=dict(color="#635a48", family="Georgia, serif"),
            thickness=12,
        ),
        xgap=3, ygap=3,
        hovertemplate="%{text}<extra></extra>",
    ))
    hm_fig.update_layout(
        height=220,
        margin=dict(l=120, r=80, t=10, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showticklabels=False, showgrid=False),
        yaxis=dict(color="#9e9078", showgrid=False),
        font=dict(size=10, color="#9e9078", family="Georgia, 'Times New Roman', serif"),
    )
    st.plotly_chart(hm_fig, config={"responsive": True})

    caption = "Clipped at ±5%. Cells with no data show 0%."
    if summary_date:
        caption += f"  ·  Data from scan: {summary_date}"
    st.caption(caption)


# ── Section 14 — Category overview table ─────────────────────────────────────

def render_category_overview(cat_data: dict, summary_date: str) -> None:
    """Render the styled category overview dataframe (content inside the expander)."""
    rows          = cat_data.get("rows", [])
    missing_names = cat_data.get("missing", [])

    if not rows:
        st.info("No scan data for this category. Run a full scan first.")
        return

    df = pd.DataFrame(rows)

    def _color_pct(val: object) -> str:
        if isinstance(val, (int, float)):
            if val > 0:
                return "color: #7db888"
            if val < 0:
                return "color: #c08080"
        return ""

    def _color_rsi(val: object) -> str:
        if isinstance(val, (int, float)):
            if val > 70:
                return "color: #c08080"
            if val < 30:
                return "color: #7db888"
        return ""

    styled = (
        df.style
        .format({
            "Price":   "${:,.2f}",
            "24h %":   "{:+.2f}%",
            "7d %":    "{:+.2f}%",
            "RSI":     "{:.1f}",
            "10d ROC": "{:+.2f}%",
        })
        .map(_color_pct, subset=["24h %", "7d %", "10d ROC"])
        .map(_color_rsi, subset=["RSI"])
    )
    st.dataframe(styled, width="stretch", hide_index=True)

    if missing_names:
        st.caption(f"No snapshot data for: {', '.join(missing_names)}. Run a full scan to populate.")
    elif summary_date:
        st.caption(f"Data from scan: {summary_date}.")
