"""
backtest.py — Signal backtesting against stored historical snapshots.

For each consecutive pair of daily snapshots the signal score of day N is
compared with the actual price direction from day N to day N+1.

Outputs:
  - Overall directional accuracy
  - Accuracy broken down by signal strength (strong / moderate / weak)
  - Accuracy broken down by signal label (e.g. "Strong Bullish -> 70% accuracy")
  - Current win/loss streak
  - Per-asset and per-category accuracy via evaluate_all_assets()
"""

from __future__ import annotations

import datetime as dt
import logging
from typing import Any

from .config import BACKTEST_WINDOW, TRACKED_ASSETS
from .errors import StorageError
from .storage import list_tracked_assets_with_history, load_snapshots

log = logging.getLogger(__name__)

# signal score thresholds used to bucket predictions
# "how confident did we sound" bucketing system, very official
_STRONG_THRESHOLD   = 6.0
_MODERATE_THRESHOLD = 3.0
# |score| < _MODERATE_THRESHOLD is "weak" — we mumbled and the market ignored us


def evaluate_signal_accuracy(
    asset_name: str,
    lookback: int = BACKTEST_WINDOW,
) -> dict:
    """
    Evaluate past signal accuracy for *asset_name*.

    Returns a dict with:
      hit_rate            — fraction of signals that predicted correct direction
      num_evaluated       — number of valid signal-outcome pairs found
      details             — list of individual records (newest first)
      avg_signal_score    — mean absolute signal score over the window
      message             — one-line human-readable summary
      by_signal_strength  — accuracy split: strong / moderate / weak
      by_label            — accuracy per signal label
      label_summaries     — list of strings like "Strong Bullish -> 70% accuracy"
    """
    # past performance does not guarantee future results. we check it anyway like optimists
    try:
        snapshots = load_snapshots(asset_name, days=lookback + 5, strict=True)
    except StorageError as exc:
        return _empty_result(
            "Historical data could not be read for backtesting.",
            error={
                "type": "storage_error",
                "exception": exc.__class__.__name__,
                "stage": "backtest_history",
                "asset": asset_name,
                "message": str(exc),
            },
        )

    if len(snapshots) < 2:
        return _empty_result("Insufficient historical data for backtesting.")  # not enough days to embarrass ourselves

    # Sort ascending so consecutive pairs (day N, day N+1) are adjacent
    ordered = sorted(snapshots, key=lambda s: s.get("date", ""))

    details: list[dict] = []
    hits      = 0
    evaluated = 0
    scores: list[float] = []

    for i in range(len(ordered) - 1):
        curr = ordered[i]
        nxt  = ordered[i + 1]

        # Skip pairs separated by more than 4 calendar days (weekend + holiday).
        # A larger gap means the "next-day" prediction spans multiple sessions,
        # which inflates or deflates apparent accuracy.
        curr_date_str = curr.get("date")
        nxt_date_str  = nxt.get("date")
        if not curr_date_str or not nxt_date_str:
            continue
        try:
            curr_date = dt.date.fromisoformat(curr_date_str)
            nxt_date  = dt.date.fromisoformat(nxt_date_str)
            if (nxt_date - curr_date).days > 4:
                continue
        except (ValueError, TypeError):
            continue  # malformed date — skip the pair entirely, don't evaluate it

        sig_score  = curr.get("signal_score")
        curr_price = curr.get("price")
        next_price = nxt.get("price")

        if sig_score is None or curr_price is None or next_price is None:
            continue
        if curr_price == 0:
            continue

        predicted_up  = sig_score > 0  # did we call it up or down
        actual_change = ((next_price - curr_price) / curr_price) * 100
        actual_up     = actual_change > 0
        correct       = predicted_up == actual_up  # were we right? ask this with shame

        hits      += int(correct)
        evaluated += 1
        scores.append(sig_score)

        details.append({
            "date":          curr.get("date"),
            "signal_score":  round(sig_score, 2),
            "signal_label":  curr.get("signal_label", ""),
            "predicted":     "up" if predicted_up else "down",
            "actual_change": round(actual_change, 2),
            "actual":        "up" if actual_up else "down",
            "correct":       correct,
        })

    if evaluated == 0:
        return _empty_result("No evaluable signal pairs found in stored history.")

    hit_rate  = hits / evaluated
    avg_score = sum(scores) / len(scores)
    pct_str   = f"{hit_rate * 100:.1f}%"
    # "strong" means we were right 65%+ of the time. a coin is 50%. we're slightly better than a coin
    quality   = "strong" if hit_rate >= 0.65 else "moderate" if hit_rate >= 0.50 else "weak"

    message = (
        f"Evaluated {evaluated} signal pair{'s' if evaluated != 1 else ''}: "
        f"{hits} correct ({pct_str} accuracy) — {quality} directional performance."
    )

    # Return newest records first for the UI
    details.reverse()

    # Accuracy by signal strength
    buckets: dict[str, dict] = {
        "strong":   {"hits": 0, "total": 0},
        "moderate": {"hits": 0, "total": 0},
        "weak":     {"hits": 0, "total": 0},
    }
    label_counts: dict[str, dict] = {}

    for d in details:
        abs_score = abs(d["signal_score"])
        if abs_score >= _STRONG_THRESHOLD:
            bucket = "strong"
        elif abs_score >= _MODERATE_THRESHOLD:
            bucket = "moderate"
        else:
            bucket = "weak"
        buckets[bucket]["total"] += 1
        if d["correct"]:
            buckets[bucket]["hits"] += 1

        lbl = d["signal_label"] or "Unknown"
        label_counts.setdefault(lbl, {"hits": 0, "total": 0})
        label_counts[lbl]["total"] += 1
        if d["correct"]:
            label_counts[lbl]["hits"] += 1

    by_signal_strength: dict[str, dict] = {}
    for bucket, data in buckets.items():
        if data["total"] > 0:
            hr = data["hits"] / data["total"]
            by_signal_strength[bucket] = {
                "hit_rate": round(hr, 4),
                "count":    data["total"],
                "summary":  (
                    f"{bucket.title()} signals ({data['total']} samples) "
                    f"-> {hr * 100:.0f}% accuracy"
                ),
            }

    # Accuracy by label
    by_label: dict[str, dict] = {}
    label_summaries: list[str] = []

    label_order = [
        "Strong Bullish", "Bullish", "Slightly Bullish",
        "Neutral",
        "Slightly Bearish", "Bearish", "Strong Bearish",
    ]
    for lbl in label_order:
        lbl_data = label_counts.get(lbl)
        if not lbl_data or lbl_data["total"] == 0:
            continue
        hr = lbl_data["hits"] / lbl_data["total"]
        by_label[lbl] = {
            "hit_rate": round(hr, 4),
            "count":    lbl_data["total"],
            "summary":  f"{lbl} -> {hr * 100:.0f}% accuracy ({lbl_data['total']} samples)",
        }
        label_summaries.append(by_label[lbl]["summary"])

    return {
        "hit_rate":           round(hit_rate, 4),
        "num_evaluated":      evaluated,
        "details":            details[:lookback],
        "avg_signal_score":   round(avg_score, 2),
        "message":            message,
        "by_signal_strength": by_signal_strength,
        "by_label":           by_label,
        "label_summaries":    label_summaries,
    }


def evaluate_all_assets(lookback: int = BACKTEST_WINDOW) -> dict:
    """
    Evaluate all assets with stored history.

    Returns {asset_name: evaluate_signal_accuracy_result + "category" key}.
    Useful for a market-wide accuracy overview.
    """
    # Build a reverse lookup: asset_name -> category
    cat_lookup: dict[str, str] = {
        name: cat
        for cat, assets in TRACKED_ASSETS.items()
        for name in assets
    }

    results: dict[str, dict] = {}
    for asset_name in list_tracked_assets_with_history():
        result = evaluate_signal_accuracy(asset_name, lookback)
        result["category"] = cat_lookup.get(asset_name, "Unknown")
        results[asset_name] = result
        log.debug(
            "Backtest %s: %s",
            asset_name,
            result["message"],
        )

    return results


def get_signal_streak(details: list[dict]) -> dict:
    """
    From a details list (newest-first), compute the current win/loss streak.
    Returns {"type": "win"|"loss"|"none", "length": int}.
    """
    if not details:
        return {"type": "none", "length": 0}

    streak_type = "win" if details[0]["correct"] else "loss"
    length = 0
    for record in details:
        if record["correct"] == (streak_type == "win"):
            length += 1
        else:
            break

    return {"type": streak_type, "length": length}


# Internal

def _empty_result(message: str, error: dict | None = None) -> dict:
    result: dict[str, Any] = {
        "hit_rate":           None,
        "num_evaluated":      0,
        "details":            [],
        "avg_signal_score":   None,
        "message":            message,
        "by_signal_strength": {},
        "by_label":           {},
        "label_summaries":    [],
    }
    if error is not None:
        result["error"] = error
    return result
