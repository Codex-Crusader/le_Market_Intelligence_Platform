"""
scan.py — Full-market snapshot pipeline.

Processes and saves snapshots for ALL tracked assets independently
of the dashboard.  Each run saves per-asset compressed JSON snapshots
and writes a hierarchical scan summary.

Usage:
    python -m pulseengine.local.scan              # process all assets, verbose
    python -m pulseengine.local.scan --quiet      # suppress per-asset log lines
    python -m pulseengine.local.scan --dry-run    # show what would run, save nothing

Structure of the scan summary (market_data/_scan_summary.json.gz):
    {
      "scan_date":  "2026-03-31",
      "scan_time":  "2026-03-31T14:00:00",
      "total":      24,
      "succeeded":  24,
      "errors":     [],
      "results": {
        "Commodities": {
          "Gold": {
            "ticker":          "GC=F",
            "signal_score":    4.5,
            "signal_label":    "Bullish",
            ...
          },
          ...
        },
        ...
      }
    }

Responsibility boundary:
  run_scan()       (this module) — batch pipeline; persists .json.gz snapshots
                                   and the scan summary; called from the CLI or
                                   a scheduled job.
  run_full_scan()  (pulseengine.core) — dashboard background daemon; returns rich
                                   in-memory objects (DataFrames, article lists);
                                   does NOT write any files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import logging
import re
from pathlib import Path

from pulseengine.core import (
    TRACKED_ASSETS,
    STORAGE_DIR,
    fetch_news_articles,
    analyse_asset,
    fetch_all_metrics_parallel,
    apply_retention_policy,
    cleanup_old_snapshots,
)

log = logging.getLogger(__name__)

_SUMMARY_FILE = Path(STORAGE_DIR) / "_scan_summary.json.gz"


def _snake_case(s: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", s).lower()


def _build_error_payload(stage: str, exc: Exception, **context) -> dict:
    payload = {
        "type": _snake_case(exc.__class__.__name__),
        "exception": exc.__class__.__name__,
        "stage": stage,
        "message": str(exc),
    }
    payload.update({k: v for k, v in context.items() if v is not None})
    return payload


def run_scan(verbose: bool = True, dry_run: bool = False) -> dict:
    """
    Run the full pipeline for every tracked asset.

    Returns a hierarchical dict:
        {category: {asset_name: scalar_summary_dict}}
    plus top-level meta fields (scan_date, errors, etc.).
    """
    started = dt.datetime.now().isoformat()
    log.info("Full market scan started at %s", started)

    if dry_run:
        log.info("DRY RUN — no snapshots will be written.")

    # fetch news once, reuse for every asset. work smarter not harder
    articles = fetch_news_articles()
    log.info("Fetched %d deduplicated articles for correlation.", len(articles))

    # Pre-fetch all asset prices in parallel and build a {ticker: change_1d} cache.
    # analyse_market_context uses this to resolve peer and benchmark lookups without
    # making additional network calls — eliminates ~50-80 redundant yfinance requests
    # that would otherwise occur across the 24-asset scan loop.
    _all_price_data = fetch_all_metrics_parallel(days=5)
    price_cache: dict[str, float] = {}
    for _cat, _cat_data in _all_price_data.items():
        for _name, _data in _cat_data.items():
            _ticker = TRACKED_ASSETS.get(_cat, {}).get(_name)
            _chg = _data.get("metrics", {}).get("change_1d")
            if _ticker and _chg is not None:
                price_cache[_ticker] = _chg
    log.info("Price cache built: %d tickers pre-fetched for context analysis.", len(price_cache))

    total   = sum(len(v) for v in TRACKED_ASSETS.values())
    done    = 0
    errors: list[dict] = []
    results: dict      = {}

    for category, asset_map in TRACKED_ASSETS.items():
        results[category] = {}
        for asset_name, ticker in asset_map.items():
            done += 1
            try:
                r = analyse_asset(
                    asset_name, ticker, category, articles,
                    with_market_ctx=True,
                    save=True,
                    price_cache=price_cache,
                )
                sig     = r["signal"]
                metrics = r["metrics"]
                mom     = r["momentum"]
                expl    = r["explanation"]

                ctx = r.get("market_ctx") or {}
                entry = {
                    "ticker":          ticker,
                    "signal_score":    sig.get("score"),
                    "signal_label":    sig.get("label"),
                    "low_news_confidence": bool(sig.get("low_news_confidence", False)),
                    "news_article_count":  int(sig.get("news_article_count", 0) or 0),
                    "price":           metrics.get("latest_price"),
                    "change_1d":       metrics.get("change_1d"),
                    "change_7d":       metrics.get("change_7d"),
                    "change_30d":      metrics.get("change_30d"),
                    "volatility":      metrics.get("volatility"),
                    "trend":           metrics.get("trend"),
                    "rsi":             mom.get("rsi"),
                    "roc_10d":         mom.get("roc_10d"),
                    "trend_strength":  mom.get("trend_strength"),
                    "momentum_accel":  mom.get("momentum_accel"),
                    "confidence":      expl.get("confidence"),
                    "verdict":         expl.get("verdict", ""),
                    "is_market_wide":  ctx.get("is_market_wide", False),
                    "is_sector_wide":  ctx.get("is_sector_wide", False),
                }
                error = r.get("error")
                if error:
                    entry["error"] = error
                    errors.append({**error, "asset": asset_name, "category": category})
                results[category][asset_name] = entry

                if verbose:
                    chg       = metrics.get("change_1d") or 0.0
                    sig_score = sig.get("score", 0.0)
                    if error:
                        log.warning(
                            "[%d/%d] %-22s %-20s ERROR: %s",
                            done, total, asset_name,
                            error.get("type", "error"), error.get("message", ""),
                        )
                    else:
                        log.info(
                            "[%d/%d] %-22s %-20s %+.1f  (%+.2f%%)",
                            done, total, asset_name, sig.get("label", ""), sig_score, chg,
                        )

            except Exception as exc:
                error = _build_error_payload(
                    "scan_asset", exc,
                    asset=asset_name, category=category, ticker=ticker,
                )
                log.error("[%d/%d] FAILED %-22s: %s", done, total, asset_name, exc)
                errors.append(error)
                results.setdefault(category, {})[asset_name] = {
                    "ticker": ticker,
                    "signal_score": None,
                    "signal_label": "Error",
                    "low_news_confidence": False,
                    "news_article_count": 0,
                    "price": None,
                    "change_1d": None,
                    "change_7d": None,
                    "change_30d": None,
                    "volatility": None,
                    "trend": None,
                    "rsi": None,
                    "roc_10d": None,
                    "trend_strength": None,
                    "momentum_accel": None,
                    "confidence": "none",
                    "verdict": "",
                    "error": error,
                }

    # Precompute global views so dashboard reads are O(1) per user.
    _all_movers: list[dict] = [
        {"name": _name, "chg": _data["change_1d"]}
        for cat_assets in results.values()
        for _name, _data in cat_assets.items()
        if _data.get("change_1d") is not None
    ]
    _all_movers.sort(key=lambda x: x["chg"], reverse=True)
    top_movers = {
        "gainers": _all_movers[:5],
        "losers":  _all_movers[-5:][::-1] if len(_all_movers) >= 5 else list(reversed(_all_movers)),
    }

    _cats       = list(TRACKED_ASSETS.keys())
    _max_assets = max((len(TRACKED_ASSETS[c]) for c in _cats), default=1)
    _hm_z:    list = []
    _hm_text: list = []
    for _cat in _cats:
        _row_z:    list = []
        _row_text: list = []
        for _name in TRACKED_ASSETS.get(_cat, {}):
            _chg = results.get(_cat, {}).get(_name, {}).get("change_1d")
            if _chg is not None:
                _row_z.append(round(_chg, 2))
                _row_text.append(f"{_name}<br>{_chg:+.1f}%")
            else:
                _row_z.append(0)
                _row_text.append(_name)
        while len(_row_z) < _max_assets:
            _row_z.append(None)
            _row_text.append("")
        _hm_z.append(_row_z)
        _hm_text.append(_row_text)

    heatmap = {
        "z":          _hm_z,
        "text":       _hm_text,
        "categories": _cats,
        "max_assets": _max_assets,
    }

    category_rows: dict = {}
    for _cat in _cats:
        _rows:    list = []
        _missing: list = []
        for _name in TRACKED_ASSETS.get(_cat, {}):
            _snap = results.get(_cat, {}).get(_name, {})
            if _snap.get("price") is not None:
                _rows.append({
                    "Asset":   _name,
                    "Signal":  _snap.get("signal_label", "—"),
                    "Price":   _snap.get("price", 0),
                    "24h %":   _snap.get("change_1d", 0) or 0,
                    "7d %":    _snap.get("change_7d", 0) or 0,
                    "Trend":   _snap.get("trend", "?"),
                    "RSI":     float(_snap.get("rsi") or 50.0),
                    "10d ROC": float(_snap.get("roc_10d") or 0.0),
                })
            else:
                _missing.append(_name)
        category_rows[_cat] = {"rows": _rows, "missing": _missing}

    scan_result = {
        "scan_date":     dt.date.today().isoformat(),
        "scan_time":     started,
        "total":         total,
        "succeeded":     total - len(errors),
        "errors":        errors,
        "results":       results,
        "top_movers":    top_movers,
        "heatmap":       heatmap,
        "category_rows": category_rows,
    }

    if not dry_run:
        _save_summary(scan_result)
        try:
            apply_retention_policy()
            deleted = cleanup_old_snapshots()
            if deleted:
                log.info("Retention cleanup: removed %d old snapshot(s).", deleted)
        except OSError as exc:
            log.warning("Retention policy failed: %s", exc)

    log.info(
        "Scan complete: %d/%d assets processed, %d error(s).",
        scan_result["succeeded"], total, len(errors),
    )
    return scan_result


def load_last_scan_summary() -> dict:
    """
    Load the most recent scan summary written by run_scan().
    Returns an empty dict if no summary exists or it cannot be read.
    """
    if not _SUMMARY_FILE.exists():
        return {}
    try:
        with gzip.open(_SUMMARY_FILE, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except (OSError, gzip.BadGzipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        log.warning("Could not load scan summary: %s", exc)
        return {}


# ── Internal ─────────────────────────────────────────────────────

def _json_default(obj: object) -> object:
    """Explicit JSON serialiser — converts known safe types, logs and stringifies anything else."""
    if isinstance(obj, (dt.date, dt.datetime)):
        return obj.isoformat()
    log.warning("Unexpected type in scan summary: %s — converting to string", type(obj).__name__)
    return str(obj)


def _save_summary(payload: dict) -> None:
    """Write hierarchical scan summary to compressed JSON."""
    try:
        _SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
        raw = json.dumps(payload, ensure_ascii=False, default=_json_default).encode("utf-8")
        with gzip.open(_SUMMARY_FILE, "wb", compresslevel=6) as fh:
            fh.write(raw)
        log.info("Scan summary saved: %s", _SUMMARY_FILE)
    except OSError as exc:
        log.warning("Could not save scan summary: %s", exc)


# ── CLI entry point ───────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="PulseEngine — Full Market Scan")
    parser.add_argument("--quiet",   action="store_true",
                        help="Suppress per-asset log lines (errors still shown)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run the pipeline but do not write any files")
    args = parser.parse_args()

    scan_summary = run_scan(verbose=not args.quiet, dry_run=args.dry_run)

    print()
    print("=" * 65)
    print(f"  Market Scan — {scan_summary['scan_date']}")
    print(f"  Assets processed: {scan_summary['succeeded']}/{scan_summary['total']}")
    if scan_summary["errors"]:
        print(f"  Errors ({len(scan_summary['errors'])}):")
        for e in scan_summary["errors"]:
            err_type = e.get("type", "error")
            message = e.get("message", e.get("error", ""))
            print(f"    [{e['category']}] {e['asset']} ({err_type}): {message}")
    print()
    print("  Top signals by magnitude:")
    all_sigs: list[tuple] = []
    for cat, assets in scan_summary["results"].items():
        for name, data in assets.items():
            score = data.get("signal_score")
            if score is not None:
                all_sigs.append((name, cat, score, data.get("signal_label", "")))
    all_sigs.sort(key=lambda x: -abs(x[2]))
    for name, cat, score, label in all_sigs[:10]:
        print(f"    {name:<22s} {label:<20s} {score:+.1f}")
    print("=" * 65)
