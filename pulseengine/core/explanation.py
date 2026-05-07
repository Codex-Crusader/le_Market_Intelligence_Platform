"""
src/explanation.py — Multi-factor explanation engine.

Single responsibility: turn structured analysis data into human-readable
narrative output.

Pipeline role (step 10 of the full engine):
  - build_explanation     : produce verdict, factor list, markdown detail,
                            confidence assessment, contradictions, and a
                            concise "why it matters" insight
  - _detect_contradictions: identify tensions between signal components
  - _build_why_it_matters : generate a 1-2 sentence actionable insight
  - _assess_confidence    : score explanation confidence and list reasons
  - _build_verdict        : compose the one-line summary sentence
"""

from __future__ import annotations

import logging

from .config import (
    PRICE_CHANGE_THRESHOLD,
    RELEVANCE_HIGH,
    RELEVANCE_MEDIUM,
    RSI_PERIOD,
)

log = logging.getLogger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

def build_explanation(
    asset_name: str,
    metrics: dict,
    related_news: list[dict],
    market_ctx: dict | None = None,
    momentum: dict | None = None,
    signal: dict | None = None,
) -> dict:
    """
    Produce a structured explanation with:
      verdict          — one-line summary
      factors          — contributing factor dicts
      detail           — long-form markdown
      confidence       — "high" / "medium" / "low" (backward-compat)
      confidence_info  — dict with score + reasoning
      contradictions   — detected signal contradictions
      why_it_matters   — concise actionable insight
    """
    if not metrics:
        return {
            "verdict":         f"No price data available for {asset_name}.",
            "factors":         [],
            "detail":          "",
            "confidence":      "none",
            "confidence_info": {"level": "none", "score": 0, "reasons": []},
            "contradictions":  [],
            "why_it_matters":  "",
        }

    momentum = momentum or {}
    signal   = signal   or {}

    price  = metrics.get("latest_price", 0.0)
    chg_1d = metrics.get("change_1d")
    chg_7d = metrics.get("change_7d")
    trend  = metrics.get("trend", "unknown")
    vol    = metrics.get("volatility", 0)
    rsi    = momentum.get("rsi", 50.0)
    roc    = momentum.get("roc_10d", 0.0)
    ts     = momentum.get("trend_strength", 0.0)

    is_significant = chg_1d is not None and abs(chg_1d) >= PRICE_CHANGE_THRESHOLD

    if chg_1d is None:
        direction_word, direction_sign = "unchanged", 0
    elif chg_1d > 0:
        direction_word, direction_sign = "up", 1
    elif chg_1d < 0:
        direction_word, direction_sign = "down", -1
    else:
        direction_word, direction_sign = "flat", 0

    factors: list[dict] = []

    # A. Price overview ────────────────────────────────────────────────────────
    detail_parts: list[str] = [
        f"## {asset_name} — Price Analysis\n",
        (
            f"**Current price:** ${price:,.4f}  \n"
            f"**24-hour change:** {_fmt_pct(chg_1d)}  \n"
            f"**7-day change:** {_fmt_pct(chg_7d)}  \n"
            f"**30-day trend:** {trend}  \n"
            f"**Daily volatility:** {vol:.2f}%\n"
        ),
    ]

    if is_significant and vol > 0:
        z_score = abs(chg_1d) / vol
        if z_score > 2:
            detail_parts.append(
                f"> This move is **{z_score:.1f}x** the normal daily volatility"
                f" — a statistically unusual event.\n"
            )
            factors.append({
                "type":   "volatility",
                "label":  "Abnormal move size",
                "detail": f"{z_score:.1f}x normal daily volatility",
            })

    # B. Momentum indicators ───────────────────────────────────────────────────
    detail_parts.append("## Momentum Indicators\n")
    rsi_note = ""
    if rsi > 70:
        rsi_note = " — overbought territory"
        factors.append({
            "type":   "rsi_overbought",
            "label":  f"RSI overbought ({rsi:.0f})",
            "detail": "RSI above 70 suggests overextension; watch for pullback",
        })
    elif rsi < 30:
        rsi_note = " — oversold territory"
        factors.append({
            "type":   "rsi_oversold",
            "label":  f"RSI oversold ({rsi:.0f})",
            "detail": "RSI below 30 suggests potential mean-reversion bounce",
        })

    detail_parts.append(
        f"**RSI ({RSI_PERIOD}-day):** {rsi:.1f}{rsi_note}  \n"
        f"**10-day Rate of Change:** {roc:+.2f}%  \n"
        f"**Trend strength (MA divergence):** {ts:+.2f}%  \n"
        f"**Momentum acceleration:** {momentum.get('momentum_accel', 0.0):+.2f}%"
        f" (recent vs prior 5d ROC)\n"
    )

    if signal:
        detail_parts.append(
            f"**Signal score:** {signal.get('score', 0):+.1f} / 10 "
            f"— **{signal.get('label', 'Neutral')}**\n"
        )

    # C. Market context ────────────────────────────────────────────────────────
    if market_ctx:
        detail_parts.append("## Market Context\n")

        if market_ctx.get("is_market_wide"):
            bench = market_ctx.get("benchmark_change")
            detail_parts.append(
                f"The **broad market also moved {_fmt_pct(bench)}**, "
                f"suggesting this is part of a **market-wide shift** rather than "
                f"something specific to {asset_name}.\n"
            )
            factors.append({
                "type":   "market_wide",
                "label":  "Market-wide movement",
                "detail": f"Benchmark also moved {_fmt_pct(bench)}",
            })

        if market_ctx.get("is_sector_wide"):
            peers     = market_ctx.get("peer_moves", {})
            peer_strs = [
                f"{n} ({_fmt_pct(c)})" for n, c in peers.items() if c is not None
            ]
            if peer_strs:
                detail_parts.append(
                    f"**Sector peers moved in the same direction:** "
                    f"{', '.join(peer_strs)}.  \n"
                    f"This points to a **sector-wide catalyst** rather than "
                    f"an {asset_name}-specific event.\n"
                )
            factors.append({
                "type":   "sector_wide",
                "label":  "Sector-wide movement",
                "detail": f"Peers: {', '.join(peer_strs)}",
            })

        if market_ctx.get("is_asset_specific"):
            detail_parts.append(
                f"Peers and the broad market did **not** move similarly. "
                f"This move appears **specific to {asset_name}**.\n"
            )
            factors.append({
                "type":   "asset_specific",
                "label":  f"{asset_name}-specific movement",
                "detail": "Peers/market did not move in the same direction",
            })

    # D. News & event analysis ─────────────────────────────────────────────────
    if related_news:
        detail_parts.append(
            f"## News Analysis ({len(related_news)} matched articles)\n"
        )

        compounds = [a.get("sentiment", {}).get("compound", 0.0) for a in related_news]
        avg_sent  = sum(compounds) / len(compounds)
        pos_count = sum(1 for c in compounds if c > 0.05)
        neg_count = sum(1 for c in compounds if c < -0.05)
        neu_count = len(compounds) - pos_count - neg_count

        if avg_sent > 0.15:
            sent_label = "predominantly positive"
        elif avg_sent < -0.15:
            sent_label = "predominantly negative"
        else:
            sent_label = "mixed / neutral"

        detail_parts.append(
            f"**Overall news sentiment:** {sent_label} (avg score: {avg_sent:+.2f})  \n"
            f"Positive: {pos_count}  Negative: {neg_count}  Neutral: {neu_count}\n"
        )

        if direction_sign != 0:
            if (direction_sign > 0 and avg_sent > 0.1) or (direction_sign < 0 and avg_sent < -0.1):
                detail_parts.append(
                    "News sentiment **aligns with price direction** — "
                    "the move is likely news-driven.\n"
                )
                factors.append({
                    "type":   "sentiment_aligned",
                    "label":  "Sentiment matches price",
                    "detail": f"News is {sent_label} while price is {direction_word}",
                })
            elif (direction_sign > 0 and avg_sent < -0.1) or (direction_sign < 0 and avg_sent > 0.1):
                detail_parts.append(
                    "**News sentiment diverges from price direction.** "
                    "Possible explanations: the news was already priced in, "
                    "contrarian trading, or technical/algorithmic factors.\n"
                )
                factors.append({
                    "type":   "sentiment_diverged",
                    "label":  "Sentiment diverges from price",
                    "detail": f"News is {sent_label} but price is {direction_word}",
                })

        # Event triggers
        all_events: dict[str, list[str]] = {}
        for article in related_news:
            for ev in article.get("events_detected", []):
                all_events.setdefault(ev["label"], []).append(ev["icon"])

        if all_events:
            detail_parts.append("### Detected Catalysts\n")
            for label, icons in all_events.items():
                count = len(icons)
                detail_parts.append(
                    f"- {icons[0]} **{label}** ({count} mention{'s' if count > 1 else ''})"
                )
                factors.append({
                    "type":   "event",
                    "label":  label,
                    "detail": f"Mentioned in {count} article(s)",
                })
            detail_parts.append("")

        # Top headlines
        detail_parts.append("### Key Headlines\n")
        for article in related_news[:7]:
            sent    = article.get("sentiment", {}).get("compound", 0.0)
            tag     = "[+]" if sent > 0.05 else "[-]" if sent < -0.05 else "[ ]"
            rel     = article.get("relevance_score", 0)
            rel_tag = (
                "HIGH" if rel >= RELEVANCE_HIGH
                else "MED" if rel >= RELEVANCE_MEDIUM
                else "LOW"
            )
            pub = ""
            if article.get("published"):
                pub = article["published"].strftime("%b %d %H:%M")
            src_w = article.get("source_weight", 1.0)
            detail_parts.append(
                f"- {tag} **[{rel_tag}]** {article['title']}  \n"
                f"  _{article['source']}_ (weight {src_w:.2f}) · {pub} · "
                f"sentiment: {sent:+.2f}"
            )
        detail_parts.append("")

    else:
        detail_parts.append("## News Analysis\n")
        detail_parts.append("No recent news articles matched this asset.\n")
        if is_significant:
            detail_parts.append(
                "Without clear news catalysts this move may be driven by:\n"
                "- Algorithmic / high-frequency trading\n"
                "- Large institutional order flow\n"
                "- Technical breakout or breakdown\n"
                "- Broader sector rotation\n"
                "- Macro factors not captured in current feeds\n"
            )
            factors.append({
                "type":   "no_news",
                "label":  "No clear news catalyst",
                "detail": "Move may be technical or flow-driven",
            })

    # E. Contradiction detection ───────────────────────────────────────────────
    contradictions = _detect_contradictions(metrics, momentum, factors, signal)
    if contradictions:
        detail_parts.append("## Signal Contradictions\n")
        for c in contradictions:
            detail_parts.append(
                f"- **{c['type'].replace('_', ' ').title()}:** {c['description']}"
            )
        detail_parts.append("")

    # F. Verdict, confidence, why-it-matters ──────────────────────────────────
    verdict         = _build_verdict(asset_name, direction_word, chg_1d, factors, related_news)
    confidence_data = _assess_confidence(
        factors, related_news, market_ctx,
        metrics=metrics,
        contradictions=contradictions,
    )
    why_it_matters = _build_why_it_matters(asset_name, momentum, factors, signal)

    if confidence_data["reasons"]:
        detail_parts.append(
            f"## Confidence Assessment: {confidence_data['level'].upper()}\n"
        )
        for reason in confidence_data["reasons"]:
            detail_parts.append(f"- {reason}")
        detail_parts.append("")

    return {
        "verdict":         verdict,
        "factors":         factors,
        "detail":          "\n".join(detail_parts),
        "confidence":      confidence_data["level"],
        "confidence_info": confidence_data,
        "contradictions":  contradictions,
        "why_it_matters":  why_it_matters,
    }


# ── Private helpers ───────────────────────────────────────────────────────────

def _detect_contradictions(
    metrics: dict,
    momentum: dict,
    factors: list[dict],
    signal: dict,
) -> list[dict]:
    """Identify tensions between different signal components."""
    contradictions: list[dict] = []
    chg_1d = metrics.get("change_1d")
    rsi    = momentum.get("rsi", 50.0)
    roc    = momentum.get("roc_10d", 0.0)
    trend  = metrics.get("trend", "sideways")

    if chg_1d and chg_1d > 2 and rsi > 70:
        contradictions.append({
            "type": "overbought_surge",
            "description": (
                f"Price surged {chg_1d:+.2f}% but RSI ({rsi:.0f}) is in "
                f"overbought territory. Near-term momentum may be unsustainable."
            ),
        })

    if chg_1d and chg_1d < -2 and rsi < 30:
        contradictions.append({
            "type": "oversold_drop",
            "description": (
                f"Price dropped {chg_1d:+.2f}% and RSI ({rsi:.0f}) signals "
                f"oversold conditions. Technical bounce is possible despite negative news flow."
            ),
        })

    if trend == "uptrend" and any(f["type"] == "sentiment_diverged" for f in factors):
        contradictions.append({
            "type": "trend_sentiment_conflict",
            "description": (
                "Price trend is upward but news sentiment is predominantly negative. "
                "This divergence may indicate the news is lagging, already priced in, "
                "or being overridden by technical buying."
            ),
        })

    sig_score = signal.get("score", 0)
    if trend == "downtrend" and sig_score > 3:
        contradictions.append({
            "type": "trend_signal_conflict",
            "description": (
                f"Signal score is bullish ({sig_score:+.1f}) but the underlying trend "
                f"is downward. A potential reversal is indicated but unconfirmed by price action."
            ),
        })

    if abs(roc) > 10 and not any(f["type"] == "event" for f in factors):
        mv = "upward" if roc > 0 else "downward"
        contradictions.append({
            "type": "momentum_no_catalyst",
            "description": (
                f"Strong {mv} momentum ({roc:+.1f}% over 10 days) with no identifiable "
                f"news catalyst. Possible algorithmic, institutional, or technical driver."
            ),
        })

    return contradictions


def _build_why_it_matters(
    asset_name: str,
    momentum: dict,
    factors: list[dict],
    signal: dict,
) -> str:
    """Generate a concise 1-2 sentence actionable insight."""
    parts: list[str] = []
    rsi       = momentum.get("rsi", 50.0)
    ts        = momentum.get("trend_strength", 0.0)
    sig_label = signal.get("label", "Neutral")

    if any(f["type"] == "market_wide" for f in factors):
        parts.append(
            f"This is a broad market event, not specific to {asset_name}. "
            "Portfolio-wide exposure matters more than single-asset positioning right now."
        )
    elif any(f["type"] == "asset_specific" for f in factors):
        parts.append(
            f"{asset_name} is diverging from its peers, suggesting an asset-specific "
            f"catalyst. Current signal is {sig_label}."
        )
    elif any(f["type"] == "sector_wide" for f in factors):
        parts.append(
            "The move is sector-wide. "
            "Watch peer assets for convergence or divergence as a leading signal."
        )

    if any(f["type"] == "sentiment_diverged" for f in factors):
        parts.append(
            "Caution: news sentiment and price direction diverge. "
            "This may indicate noise-driven trading or a news lag."
        )

    if rsi > 70:
        parts.append(
            f"RSI at {rsi:.0f} flags overbought conditions. "
            "Watch for short-term mean reversion."
        )
    elif rsi < 30:
        parts.append(
            f"RSI at {rsi:.0f} flags oversold conditions. "
            "A technical bounce is possible."
        )

    if not parts:
        if abs(ts) > 2:
            direction = "positive" if ts > 0 else "negative"
            parts.append(
                f"Trend momentum is {direction} ({ts:+.1f}%). "
                "Monitor for continuation or reversal in the next 24-48 hours."
            )
        else:
            parts.append(
                f"{asset_name} is showing limited directional signal. "
                "Wait for clearer momentum before acting on a directional view."
            )

    return " ".join(parts[:2])


def _build_verdict(
    name: str,
    direction: str,
    change: float | None,
    factors: list[dict],
    news: list[dict],
) -> str:
    if change is None:
        return f"{name} — no recent price data."

    parts = [f"{name} is **{direction} {abs(change):.2f}%** today"]

    event_factors = [f for f in factors if f["type"] == "event"]
    if event_factors:
        parts.append(f"likely driven by **{event_factors[0]['label']}**")
    elif any(f["type"] == "market_wide" for f in factors):
        parts.append("as part of a **broad market move**")
    elif any(f["type"] == "sector_wide" for f in factors):
        parts.append("in line with a **sector-wide shift**")
    elif any(f["type"] == "sentiment_aligned" for f in factors):
        if news:
            parts.append(
                f"supported by **{len(news)} related news article"
                f"{'s' if len(news) > 1 else ''}**"
            )
    elif any(f["type"] == "no_news" for f in factors):
        parts.append("with **no clear news catalyst** (possibly technical)")
    else:
        parts.append("with limited signal from available data")

    return ", ".join(parts) + "."


def _assess_confidence(
    factors: list[dict],
    news: list[dict],
    ctx: dict | None,
    metrics: dict | None = None,
    contradictions: list[dict] | None = None,
) -> dict:
    """
    Return a dict: {level, score, reasons, increases, decreases}.

    Score increases when:
      - Multiple high-quality sources agree (weight >= 1.2, at least 2)
      - Sentiment aligns with price direction
      - Event trigger detected
      - Strong price move (|change_1d| >= 2 %)
      - Market or sector context confirms direction

    Score decreases when:
      - Contradictions detected
      - Low news coverage (< 2 articles)
      - Weak price move (|change_1d| < 0.5 %)
      - Sentiment contradicts price direction
    """
    score     = 0
    increases: list[str] = []
    decreases: list[str] = []

    # Increases ───────────────────────────────────────────────────────────────
    if news:
        hq = [a for a in news if a.get("source_weight", 1.0) >= 1.2]
        if len(hq) >= 2:
            score += 3
            increases.append(
                f"{len(hq)} high-quality sources agree (credibility weight >= 1.2x)"
            )
        else:
            n = min(len(news), 3)
            score += n
            increases.append(
                f"{len(news)} matched news article{'s' if len(news) != 1 else ''} (+{n})"
            )

    if any(f["type"] == "sentiment_aligned" for f in factors):
        score += 2
        increases.append("news sentiment aligns with price direction")

    event_factors = [f for f in factors if f["type"] == "event"]
    if event_factors:
        score += 3
        labels = [f["label"] for f in event_factors[:2]]
        increases.append(f"event trigger detected: {', '.join(labels)}")

    chg_1d = metrics.get("change_1d") if metrics else None
    if chg_1d is not None and abs(chg_1d) >= 2.0:
        score += 1
        increases.append(f"strong price move ({chg_1d:+.2f}%)")

    if ctx:
        if ctx.get("is_market_wide"):
            score += 2
            increases.append("broad market context confirms direction")
        elif ctx.get("is_sector_wide"):
            score += 1
            increases.append("sector context confirms direction")

    # Decreases ───────────────────────────────────────────────────────────────
    if contradictions:
        penalty = min(len(contradictions) * 2, 3)
        score -= penalty
        decreases.append(
            f"{len(contradictions)} signal contradiction(s) detected (-{penalty})"
        )

    if not news:
        score -= 2
        decreases.append("no matched news articles (-2)")
    elif len(news) < 2:
        score -= 1
        decreases.append("very few matched news articles (-1)")

    if chg_1d is not None and abs(chg_1d) < 0.5:
        score -= 1
        decreases.append(
            f"weak price move ({chg_1d:+.2f}%) — limited signal clarity (-1)"
        )

    if any(f["type"] == "sentiment_diverged" for f in factors):
        score -= 2
        decreases.append("news sentiment contradicts price direction (-2)")

    if chg_1d is not None and abs(chg_1d) >= 2.0 and not event_factors and not news:
        score -= 1
        decreases.append("significant move with no identifiable catalyst (-1)")

    reasons = increases + decreases
    if not reasons:
        reasons = ["limited signal data available"]

    if score >= 7:
        level = "high"
    elif score >= 4:
        level = "medium"
    else:
        level = "low"

    return {
        "level":     level,
        "score":     score,
        "reasons":   reasons,
        "increases": increases,
        "decreases": decreases,
    }


# ── Formatting helper ─────────────────────────────────────────────────────────

def _fmt_pct(val: float | None) -> str:
    if val is None:
        return "N/A"
    sign = "+" if val > 0 else ""
    return f"{sign}{val:.2f}%"
