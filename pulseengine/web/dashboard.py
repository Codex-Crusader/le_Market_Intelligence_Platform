"""Restricted stateless Streamlit demo for PulseEngine."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pulseengine.core import (  # noqa: E402
    DASHBOARD_ICON,
    DASHBOARD_LAYOUT,
    DASHBOARD_TITLE,
    DEFAULT_CATEGORY,
    DataFetchError,
    TRACKED_ASSETS,
    analyse_market_context,
    build_explanation,
    cluster_articles,
    compute_momentum_metrics,
    compute_price_metrics,
    compute_signal_score,
    correlate_news,
    fetch_all_metrics_parallel,
    fetch_news_articles,
    fetch_price_history,
)


st.set_page_config(
    page_title=f"{DASHBOARD_TITLE} | Web Demo",
    page_icon=DASHBOARD_ICON,
    layout=DASHBOARD_LAYOUT,  # type: ignore[arg-type]
)

st.title("PulseEngine Web Demo")
st.caption(
    "A lightweight live preview of the shared engine. Locked features stay local-only."
)

st.info(
    "This demo is stateless: no snapshot storage, no backtesting, no local model\n"
    "inference, and no arbitrary ticker lookup. Install the local app for the full experience."
)


def _format_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}%"


def _build_live_analysis(asset_name: str, ticker: str, category: str) -> dict:
    """Build a live, read-only analysis for the selected asset."""
    try:
        history = fetch_price_history(ticker)
    except DataFetchError as exc:
        return {"error": str(exc), "history": None, "metrics": {}, "momentum": {}}

    if history is None or history.empty:
        return {
            "error": f"No price history available for {asset_name}.",
            "history": history,
            "metrics": {},
            "momentum": {},
            "news": [],
            "clusters": {},
            "market_ctx": None,
            "signal": {"score": 0.0, "label": "No Data"},
            "explanation": {"verdict": "No price data available."},
        }

    metrics = compute_price_metrics(history)
    momentum = compute_momentum_metrics(history)
    articles = fetch_news_articles()
    news = correlate_news(asset_name, articles)
    clusters = cluster_articles(news)
    market_ctx = None
    if metrics.get("change_1d") is not None:
        market_ctx = analyse_market_context(asset_name, category, metrics.get("change_1d"))
    signal = compute_signal_score(metrics, momentum, news, market_ctx, category=category)
    explanation = build_explanation(
        asset_name,
        metrics,
        news,
        market_ctx=market_ctx,
        momentum=momentum,
        signal=signal,
    )
    return {
        "error": None,
        "history": history,
        "metrics": metrics,
        "momentum": momentum,
        "news": news,
        "clusters": clusters,
        "market_ctx": market_ctx,
        "signal": signal,
        "explanation": explanation,
    }


def _render_locked_features() -> None:
    st.subheader("Local-only features")
    st.markdown(
        "- Arbitrary ticker lookup\n"
        "- Backtesting\n"
        "- Historical snapshots\n"
        "- Export to CSV / PDF\n"
        "- Offline mode\n"
        "- Local model inference"
    )
    st.caption("Run the local app to unlock these capabilities.")
    st.code("streamlit run pulseengine/local/dashboard.py", language="bash")


st.sidebar.header("Demo controls")
categories = list(TRACKED_ASSETS.keys())
default_index = categories.index(DEFAULT_CATEGORY) if DEFAULT_CATEGORY in categories else 0
selected_category = st.sidebar.selectbox("Category", categories, index=default_index)
asset_names = list(TRACKED_ASSETS[selected_category].keys())
selected_asset = st.sidebar.selectbox("Asset", asset_names)
ticker = TRACKED_ASSETS[selected_category][selected_asset]

selected = _build_live_analysis(selected_asset, ticker, selected_category)

if selected.get("error"):
    st.warning(selected["error"])
else:
    metrics = selected["metrics"]
    momentum = selected["momentum"]
    signal = selected["signal"]
    explanation = selected["explanation"]
    history = selected["history"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Signal", signal.get("label", "n/a"), f"{signal.get('score', 0.0):+.1f}")
    c2.metric("Price", f"${metrics.get('latest_price', 0.0):,.2f}", _format_pct(metrics.get("change_1d")))
    c3.metric("RSI", f"{momentum.get('rsi', 0.0):.1f}")
    c4.metric("ROC 10d", _format_pct(momentum.get("roc_10d")))

    st.subheader("Why it matters")
    st.write(explanation.get("why_it_matters") or explanation.get("verdict", ""))

    if history is not None and not history.empty and "Close" in history.columns:
        st.subheader("Price chart")
        st.line_chart(history["Close"])

    st.subheader("News sentiment")
    if selected["news"]:
        for article in selected["news"][:5]:
            sent = article.get("sentiment", {}).get("compound", 0.0)
            st.markdown(f"- **{article.get('title', 'Untitled')}** ({_format_pct(sent * 100)})")
    else:
        st.caption("No relevant articles matched this asset.")

    st.subheader("Current market context")
    market_ctx = selected.get("market_ctx") or {}
    context_cols = st.columns(3)
    context_cols[0].metric("Sector-wide", str(bool(market_ctx.get("is_sector_wide"))))
    context_cols[1].metric("Market-wide", str(bool(market_ctx.get("is_market_wide"))))
    context_cols[2].metric("Asset-specific", str(bool(market_ctx.get("is_asset_specific"))))

    _render_locked_features()


st.divider()
st.subheader("Market heatmap and category overview")
st.caption("Computed on demand from live price data only. No state is written to disk.")

if st.button("Build market overview"):
    overview = fetch_all_metrics_parallel(days=5)
    rows: list[dict] = []
    asset_order = [asset for category in TRACKED_ASSETS.values() for asset in category]
    categories = list(TRACKED_ASSETS.keys())

    matrix: list[list[float | None]] = []
    labels: list[list[str]] = []
    for category in categories:
        row_values: list[float | None] = []
        row_labels: list[str] = []
        for asset_name in asset_order:
            asset_map = TRACKED_ASSETS.get(category, {})
            if asset_name in asset_map:
                data = overview.get(category, {}).get(asset_name, {})
                metrics = data.get("metrics", {})
                momentum = data.get("momentum", {})
                rows.append(
                    {
                        "Category": category,
                        "Asset": asset_name,
                        "Ticker": asset_map[asset_name],
                        "Price": metrics.get("latest_price"),
                        "Change 1d": metrics.get("change_1d"),
                        "RSI": momentum.get("rsi"),
                        "Trend": metrics.get("trend"),
                    }
                )
                row_values.append(metrics.get("change_1d"))
                row_labels.append(f"{asset_name}<br>{_format_pct(metrics.get('change_1d'))}")
            else:
                row_values.append(None)
                row_labels.append("")
        matrix.append(row_values)
        labels.append(row_labels)

    fig = go.Figure(
        data=go.Heatmap(
            z=matrix,
            x=asset_order,
            y=categories,
            text=labels,
            colorscale="RdYlGn",
            zmid=0,
            hovertemplate="%{y} / %{x}<br>Change: %{z:+.2f}%<extra></extra>",
        )
    )
    fig.update_layout(height=380, margin=dict(l=20, r=20, t=40, b=20))

    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.caption("Click to load the full market overview.")
