"""
storage.py - Lightweight compressed JSON storage for historical signal data.

File naming:
    market_data/<AssetName>_YYYYMMDD.json.gz

Retention tiers:
    <= STORAGE_FULL_DETAIL_DAYS  : full snapshot (all fields + headlines)
    <= STORAGE_REDUCED_DETAIL_DAYS: reduced snapshot (no headlines, fewer fields)
    >  STORAGE_MAX_DAYS           : deleted by cleanup_old_snapshots()
"""

from __future__ import annotations

import datetime as dt
import gzip
import json
import logging
import os
import threading
import uuid
from pathlib import Path

from .config import (
    SNAPSHOT_LOAD_LIMIT,
    STORAGE_DIR,
    STORAGE_FULL_DETAIL_DAYS,
    STORAGE_MAX_DAYS,
    STORAGE_REDUCED_DETAIL_DAYS,
    TRACKED_ASSETS,
)
from .errors import StorageError

log = logging.getLogger(__name__)
_storage_path = Path(STORAGE_DIR)

# per-asset write locks — one bouncer per asset. orderly queue. no shoving
_asset_locks: dict[str, threading.Lock] = {}
_asset_locks_mutex = threading.Lock()


def _get_asset_lock(asset_name: str) -> threading.Lock:
    """Return the dedicated lock for *asset_name*, creating it on first use."""
    with _asset_locks_mutex:
        if asset_name not in _asset_locks:
            _asset_locks[asset_name] = threading.Lock()
        return _asset_locks[asset_name]


# fields kept in reduced-detail snapshots — the diet version. all the shame, half the data
_REDUCED_FIELDS = {
    "asset", "date", "price", "change_1d", "signal_score", "signal_label",
    "trend", "rsi", "roc_10d", "trend_strength",
    "is_market_wide", "is_sector_wide",  # context flags are booleans — cheap to keep
}


# Internal helpers

def _ensure_dir() -> None:
    # make the directory or face consequences
    _storage_path.mkdir(parents=True, exist_ok=True)


def _asset_prefix(asset_name: str) -> str:
    return asset_name.replace(" ", "_").replace("/", "-").replace("&", "and")


# Reverse map: storage prefix → asset display name.  Built once at module load
# so list_tracked_assets_with_history() can resolve names from filenames alone
# without reading any snapshot files.
_PREFIX_TO_ASSET: dict[str, str] = {
    _asset_prefix(name): name
    for assets in TRACKED_ASSETS.values()
    for name in assets
}


def _snapshot_path(asset_name: str, date: dt.date) -> Path:
    candidate = _storage_path / f"{_asset_prefix(asset_name)}_{date.strftime('%Y%m%d')}.json.gz"
    # Guard against path traversal: the resolved path must stay inside storage_path
    try:
        candidate.resolve().relative_to(_storage_path.resolve())
    except ValueError:
        raise StorageError(f"Path traversal blocked for asset name: {asset_name!r}")
    return candidate


def _read_gz(path: Path) -> dict:
    with gzip.open(path, "rb") as fh:
        raw = fh.read().decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StorageError(f"Corrupted snapshot {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise StorageError(
            f"Invalid snapshot format in {path.name}: expected dict, got {type(data).__name__}"
        )
    return data


def _write_gz(path: Path, data: dict) -> None:
    # atomic write: scribble on a UNIQUELY NAMED temp file, THEN swap it in.
    # uuid suffix means two concurrent writers for the same asset never clobber each other's draft.
    # corruption is for politicians, not our files
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    uid = uuid.uuid4().hex[:12]  # 12 hex chars — astronomically unlikely to collide. unlike my trades
    tmp = path.with_name(f"{path.stem}.{uid}.tmp")
    try:
        os.makedirs(path.parent, exist_ok=True)  # directory must exist. no excuses. no FileNotFoundError
        with gzip.open(tmp, "wb", compresslevel=6) as fh:
            fh.write(raw)
        if tmp.exists():  # belt AND suspenders — only replace if the temp actually landed
            os.replace(tmp, path)  # atomic on POSIX; best-effort on Windows. still better than nothing
        else:
            raise FileNotFoundError(f"Temp file vanished before replace: {tmp}")
    except Exception as _write_exc:
        log.error("Snapshot write failed for %s: %s", path.name, _write_exc)
        try:
            tmp.unlink(missing_ok=True)  # clean up the evidence before we raise
        except OSError:
            pass
        raise


# Public API
# what can I say? I am a cheap man.

# thresholds for "has anything actually changed enough to bother rewriting"
_PRICE_WRITE_THRESHOLD  = 0.01   # ignore sub-cent price drift
_SCORE_WRITE_THRESHOLD  = 0.5    # ignore signal score wobble below 0.5


def _snapshot_unchanged(path: Path, new_data: dict) -> bool:
    """
    Return True if the on-disk snapshot is close enough to *new_data* that
    rewriting would be pointless.  Falls back to False (always write) on any
    read error — better to write once too many than to skip a real update.
    """
    if not path.exists():
        return False
    try:
        existing = _read_gz(path)
    except (OSError, ValueError, StorageError):
        return False  # corrupted existing file — overwrite it. no mercy

    # qualitative fields: any change → write immediately
    if existing.get("signal_label") != new_data.get("signal_label"):
        return False
    if existing.get("trend") != new_data.get("trend"):
        return False
    if existing.get("is_market_wide") != new_data.get("is_market_wide"):
        return False
    if existing.get("is_sector_wide") != new_data.get("is_sector_wide"):
        return False

    # price: only skip if movement is trivial
    ep = float(existing.get("price") or 0.0)
    np_ = float(new_data.get("price") or 0.0)
    if abs(ep - np_) > _PRICE_WRITE_THRESHOLD:
        return False

    # signal score: only skip if delta is noise
    es = float(existing.get("signal_score") or 0.0)
    ns = float(new_data.get("signal_score") or 0.0)
    if abs(es - ns) > _SCORE_WRITE_THRESHOLD:
        return False

    return True  # nothing meaningful changed. we are too lazy to write. and that is correct


def save_snapshot(
    asset_name: str,
    metrics: dict,
    momentum: dict,
    signal: dict,
    top_headlines: list[dict],
    market_ctx: dict | None = None,
) -> None:
    """
    Persist a lightweight daily snapshot for *asset_name*.
    Existing file for today is overwritten so latest intraday values win.

    Parameters
    ----------
    asset_name    : human-readable asset name used as the file prefix
    metrics       : output of compute_price_metrics()
    momentum      : output of compute_momentum_metrics()
    signal        : output of compute_signal_score()
    top_headlines : list of correlated article dicts; top 5 titles/sentiments
                    are stored in full-detail snapshots
    market_ctx    : result of analyse_market_context(), or None when context
                    analysis was skipped.  When provided, ``is_market_wide`` and
                    ``is_sector_wide`` are written into the snapshot so historical
                    data and backtesting results include context flags.
    """
    _ensure_dir()
    today = dt.date.today()
    path  = _snapshot_path(asset_name, today)

    headlines = [
        {
            "title":     h.get("title", ""),
            "source":    h.get("source", ""),
            "sentiment": round(
                h.get("sentiment", {}).get("compound", 0.0)
                if isinstance(h.get("sentiment"), dict)
                else 0.0,
                4,
            ),
        }
        for h in top_headlines[:5]
    ]

    snapshot = {
        "asset":          asset_name,
        "date":           today.isoformat(),
        "price":          metrics.get("latest_price"),
        "change_1d":      metrics.get("change_1d"),
        "change_7d":      metrics.get("change_7d"),
        "change_30d":     metrics.get("change_30d"),
        "volatility":     metrics.get("volatility"),
        "trend":          metrics.get("trend"),
        "rsi":            momentum.get("rsi"),
        "roc_10d":        momentum.get("roc_10d"),
        "trend_strength": momentum.get("trend_strength"),
        "momentum_accel": momentum.get("momentum_accel"),
        "signal_score":   signal.get("score"),
        "signal_label":   signal.get("label"),
        "is_market_wide": market_ctx.get("is_market_wide") if market_ctx else None,
        "is_sector_wide": market_ctx.get("is_sector_wide") if market_ctx else None,
        "headlines":      headlines,
    }

    # skip the write if nothing meaningful has changed — stop thrashing the disk for no reason
    if _snapshot_unchanged(path, snapshot):
        log.debug("Snapshot unchanged for %s — skipping write.", asset_name)
        return

    # one writer per asset at a time. no queue jumping, no temp-file collisions
    with _get_asset_lock(asset_name):
        try:
            _write_gz(path, snapshot)
            log.debug("Saved snapshot: %s", path.name)
        except Exception as exc:
            log.warning("Snapshot write failed for %s: %s", asset_name, exc)


def load_snapshots(asset_name: str, days: int = 30, strict: bool = False) -> list[dict]:
    """
    Return stored snapshots for *asset_name* within the last *days* days,
    sorted newest-first.
    """
    if not _storage_path.exists():
        return []

    cutoff = dt.date.today() - dt.timedelta(days=days)
    prefix = _asset_prefix(asset_name)
    snapshots: list[dict] = []

    for path in _storage_path.glob(f"{prefix}_*.json.gz"):
        try:
            date_str = path.name.replace(".json.gz", "").rsplit("_", 1)[-1]
            date = dt.datetime.strptime(date_str, "%Y%m%d").date()
            if date < cutoff:
                continue
            snapshots.append(_read_gz(path))
        except Exception as exc:
            if strict:
                raise StorageError(f"Snapshot read failed for {path.name}") from exc
            log.warning("Snapshot read failed (%s): %s", path.name, exc)

    snapshots.sort(key=lambda s: s.get("date", ""), reverse=True)
    return snapshots


def load_recent_snapshots(
    asset_name: str,
    limit: int = SNAPSHOT_LOAD_LIMIT,
    strict: bool = False,
) -> list[dict]:
    """
    Return the most recent *limit* snapshots for *asset_name*,
    regardless of how old they are.  Sorted newest-first.
    Loading only a fixed slice keeps memory usage bounded.
    """
    if not _storage_path.exists():
        return []

    prefix = _asset_prefix(asset_name)
    candidates: list[tuple[dt.date, Path]] = []

    for path in _storage_path.glob(f"{prefix}_*.json.gz"):
        try:
            date_str = path.name.replace(".json.gz", "").rsplit("_", 1)[-1]
            date = dt.datetime.strptime(date_str, "%Y%m%d").date()
            candidates.append((date, path))
        except ValueError:
            pass

    # Sort newest-first, take only last `limit` files
    candidates.sort(key=lambda x: x[0], reverse=True)
    candidates = candidates[:limit]

    snapshots: list[dict] = []
    for _, path in candidates:
        try:
            snapshots.append(_read_gz(path))
        except Exception as exc:
            if strict:
                raise StorageError(f"Snapshot read failed for {path.name}") from exc
            log.warning("Snapshot read failed (%s): %s", path.name, exc)

    snapshots.sort(key=lambda s: s.get("date", ""), reverse=True)
    return snapshots


def get_historical_features(
    asset_name: str,
    limit: int = SNAPSHOT_LOAD_LIMIT,
    strict: bool = False,
) -> dict:
    """
    Derive historical context features from stored snapshots.

    Returns:
        signal_consistency  — fraction of last N signals pointing same direction as latest
        trend_persistence   — consecutive days current trend has held
        today_vs_yesterday  — dict comparing latest two snapshots on key fields
        available           — number of snapshots found
    """
    snaps = load_recent_snapshots(asset_name, limit, strict=strict)

    empty: dict[str, object] = {
        "signal_consistency": None,
        "trend_persistence":  0,
        "today_vs_yesterday": {},
        "available":          len(snaps),
    }

    if len(snaps) < 2:
        return empty

    # Signal consistency
    latest_score = snaps[0].get("signal_score", 0) or 0
    if latest_score > 0:
        latest_dir = 1
    elif latest_score < 0:
        latest_dir = -1
    else:
        latest_dir = 0

    if latest_dir != 0:
        same_dir = sum(
            1 for s in snaps
            if (
                1 if (s.get("signal_score") or 0) > 0
                else -1 if (s.get("signal_score") or 0) < 0
                else 0
            ) == latest_dir
        )
        signal_consistency = round(same_dir / len(snaps), 3)
    else:
        signal_consistency = None

    # Trend persistence: consecutive days with the same trend label
    latest_trend = snaps[0].get("trend", "")
    trend_persistence = 0
    for s in snaps:
        if s.get("trend") == latest_trend and latest_trend:
            trend_persistence += 1
        else:
            break

    # Today vs yesterday for key scalar fields
    today_snap     = snaps[0]
    yesterday_snap = snaps[1]
    compare_fields = ["price", "signal_score", "rsi", "roc_10d", "trend_strength"]
    today_vs_yesterday: dict[str, dict] = {}
    for field in compare_fields:
        t_val = today_snap.get(field)
        y_val = yesterday_snap.get(field)
        if t_val is not None and y_val is not None:
            try:
                t_float = float(t_val)
                y_float = float(y_val)
                today_vs_yesterday[field] = {
                    "today":     t_float,
                    "yesterday": y_float,
                    "change":    round(t_float - y_float, 4),
                }
            except (TypeError, ValueError):
                pass

    return {
        "signal_consistency":  signal_consistency,
        "trend_persistence":   trend_persistence,
        "today_vs_yesterday":  today_vs_yesterday,
        "available":           len(snaps),
    }


def apply_retention_policy() -> int:
    """
    Re-write older snapshots to reduced-detail format to save space.
    # spring cleaning but for market data. Marie Kondo said delete anything that doesn't spark joy
    Snapshots between STORAGE_FULL_DETAIL_DAYS+1 and STORAGE_REDUCED_DETAIL_DAYS
    days old are stripped of heavy fields (headlines, change_7d, change_30d,
    volatility, momentum_accel) if they still contain those fields.

    Returns the number of snapshots rewritten.
    """
    if not _storage_path.exists():
        return 0

    today    = dt.date.today()
    full_cutoff    = today - dt.timedelta(days=STORAGE_FULL_DETAIL_DAYS)
    reduced_cutoff = today - dt.timedelta(days=STORAGE_REDUCED_DETAIL_DAYS)
    rewritten = 0

    for path in _storage_path.glob("*.json.gz"):
        if path.name.startswith("_"):
            continue  # skip meta files like _scan_summary.json.gz
        try:
            date_str = path.name.replace(".json.gz", "").rsplit("_", 1)[-1]
            date = dt.datetime.strptime(date_str, "%Y%m%d").date()
        except ValueError:
            continue

        # Only target: older than full-detail window, within reduced window
        if date >= full_cutoff or date < reduced_cutoff:
            continue

        try:
            data = _read_gz(path)
            if "headlines" not in data and "change_7d" not in data:
                continue  # already reduced, skip
            reduced = {k: v for k, v in data.items() if k in _REDUCED_FIELDS}
            _write_gz(path, reduced)
            rewritten += 1
            log.debug("Applied reduced retention to %s", path.name)
        except Exception as exc:
            log.warning("Retention policy failed for %s: %s", path.name, exc)

    if rewritten:
        log.info("Retention policy: rewrote %d snapshot(s) to reduced detail.", rewritten)
    return rewritten


def cleanup_old_snapshots(days_to_keep: int = STORAGE_MAX_DAYS) -> int:
    """
    Delete snapshots older than *days_to_keep*.
    Returns the number of files deleted.
    """
    # out with the old. delete delete delete. no mercy. no refunds
    if not _storage_path.exists():
        return 0

    cutoff  = dt.date.today() - dt.timedelta(days=days_to_keep)
    deleted = 0

    for path in _storage_path.glob("*.json.gz"):
        if path.name.startswith("_"):
            continue
        try:
            date_str = path.name.replace(".json.gz", "").rsplit("_", 1)[-1]
            if dt.datetime.strptime(date_str, "%Y%m%d").date() < cutoff:
                path.unlink()
                deleted += 1
        except (ValueError, OSError):
            pass

    if deleted:
        log.info("Cleaned up %d old snapshot(s).", deleted)
    return deleted


def list_tracked_assets_with_history() -> list[str]:
    """Return asset names that have at least one stored snapshot.

    Derives names from filenames alone (no file reads) using the pre-built
    _PREFIX_TO_ASSET reverse map, making this O(files) instead of O(files × parse).
    """
    if not _storage_path.exists():
        return []
    prefixes: set[str] = set()
    for path in _storage_path.glob("*.json.gz"):
        if path.name.startswith("_"):
            continue
        stem = path.name[: -len(".json.gz")]       # strip extension
        prefix = stem.rsplit("_", 1)[0]            # strip _YYYYMMDD suffix
        prefixes.add(prefix)
    return sorted(_PREFIX_TO_ASSET[p] for p in prefixes if p in _PREFIX_TO_ASSET)
