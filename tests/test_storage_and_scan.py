"""Storage and integration tests for Issue #2 coverage goals."""

from __future__ import annotations

import datetime as dt
import gzip
import json
from pathlib import Path

from app.backtest import evaluate_signal_accuracy
from app.scan import run_scan
from storage import storage


def _write_snapshot_file(base_dir: Path, asset: str, date: dt.date, payload: dict) -> Path:
    safe = asset.replace(" ", "_").replace("/", "-").replace("&", "and")
    path = base_dir / f"{safe}_{date.strftime('%Y%m%d')}.json.gz"
    with gzip.open(path, "wb") as fh:
        fh.write(json.dumps(payload).encode("utf-8"))
    return path


def test_storage_round_trip_save_then_load(storage_dir):
    """Saving and then loading a snapshot should preserve key scalar fields."""
    metrics = {
        "latest_price": 2100.5,
        "change_1d": 1.25,
        "change_7d": 2.5,
        "change_30d": 4.75,
        "volatility": 0.9,
        "trend": "uptrend",
    }
    momentum = {"rsi": 58.0, "roc_10d": 3.2, "trend_strength": 1.4, "momentum_accel": 0.3}
    signal = {"score": 4.4, "label": "Bullish"}
    headlines = [{"title": "Gold rallies", "source": "Reuters", "sentiment": {"compound": 0.5}}]

    storage.save_snapshot("Gold", metrics, momentum, signal, headlines)
    loaded = storage.load_snapshots("Gold", days=2, strict=True)

    assert len(loaded) == 1
    snap = loaded[0]
    assert snap["asset"] == "Gold"
    assert snap["price"] == 2100.5
    assert snap["signal_score"] == 4.4
    assert snap["signal_label"] == "Bullish"


def test_retention_policy_and_cleanup_with_temp_dir(storage_dir):
    """Retention should reduce medium-aged snapshots and cleanup should delete very old ones."""
    today = dt.date.today()
    medium_date = today - dt.timedelta(days=10)
    old_date = today - dt.timedelta(days=40)
    recent_date = today - dt.timedelta(days=2)

    medium_payload = {
        "asset": "Gold",
        "date": medium_date.isoformat(),
        "price": 2000.0,
        "change_1d": 1.1,
        "change_7d": 2.2,
        "change_30d": 3.3,
        "volatility": 0.8,
        "trend": "uptrend",
        "rsi": 60.0,
        "roc_10d": 2.4,
        "trend_strength": 1.2,
        "momentum_accel": 0.2,
        "signal_score": 4.0,
        "signal_label": "Bullish",
        "headlines": [{"title": "x"}],
    }
    old_payload = dict(medium_payload, date=old_date.isoformat())
    recent_payload = dict(medium_payload, date=recent_date.isoformat())

    medium_path = _write_snapshot_file(storage_dir, "Gold", medium_date, medium_payload)
    old_path = _write_snapshot_file(storage_dir, "Gold", old_date, old_payload)
    recent_path = _write_snapshot_file(storage_dir, "Gold", recent_date, recent_payload)

    rewritten = storage.apply_retention_policy()
    assert rewritten >= 1

    with gzip.open(medium_path, "rb") as fh:
        reduced = json.loads(fh.read().decode("utf-8"))
    assert "headlines" not in reduced
    assert "signal_score" in reduced
    assert recent_path.exists()

    deleted = storage.cleanup_old_snapshots(days_to_keep=30)
    assert deleted >= 1
    assert not old_path.exists()


def test_run_scan_dry_run_completes_without_writing(mocker):
    """Dry-run scans should complete and skip persistence of summary files."""
    mocker.patch("app.scan.fetch_news_articles", return_value=[])
    mocker.patch(
        "app.scan.analyse_asset",
        return_value={
            "signal": {"score": 0.0, "label": "Neutral"},
            "metrics": {
                "latest_price": 100.0,
                "change_1d": 0.0,
                "change_7d": 0.0,
                "change_30d": 0.0,
                "volatility": 0.0,
                "trend": "sideways",
            },
            "momentum": {"rsi": 50.0, "roc_10d": 0.0, "trend_strength": 0.0, "momentum_accel": 0.0},
            "explanation": {"confidence": "low", "verdict": "Test"},
            "error": None,
        },
    )
    save_summary = mocker.patch("pulseengine.local.scan._save_summary")

    result = run_scan(verbose=False, dry_run=True)

    assert result["total"] > 0
    assert result["succeeded"] == result["total"]
    assert result["errors"] == []
    save_summary.assert_not_called()


def test_evaluate_signal_accuracy_with_synthetic_snapshots(storage_dir):
    """Backtest evaluation should produce a valid hit-rate on synthetic history."""
    asset = "Gold"
    today = dt.date.today()

    d1 = today - dt.timedelta(days=3)
    d2 = today - dt.timedelta(days=2)
    d3 = today - dt.timedelta(days=1)

    _write_snapshot_file(
        storage_dir,
        asset,
        d1,
        {"asset": asset, "date": d1.isoformat(), "price": 100.0, "signal_score": 2.0, "signal_label": "Bullish"},
    )
    _write_snapshot_file(
        storage_dir,
        asset,
        d2,
        {"asset": asset, "date": d2.isoformat(), "price": 102.0, "signal_score": -2.0, "signal_label": "Bearish"},
    )
    _write_snapshot_file(
        storage_dir,
        asset,
        d3,
        {"asset": asset, "date": d3.isoformat(), "price": 101.0, "signal_score": 1.0, "signal_label": "Bullish"},
    )

    result = evaluate_signal_accuracy(asset, lookback=10)

    assert result["num_evaluated"] >= 2
    assert 0.0 <= result["hit_rate"] <= 1.0
    assert isinstance(result["details"], list)
