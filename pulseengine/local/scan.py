"""Canonical local batch-scan entry point."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.scan import run_scan


def main() -> None:
    """Run the local full-market scan CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="PulseEngine — Full Market Scan")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-asset log lines (errors still shown)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the pipeline but do not write any files",
    )
    args = parser.parse_args()

    scan_summary = run_scan(verbose=not args.quiet, dry_run=args.dry_run)

    print()
    print("=" * 65)
    print(f"  Market Scan — {scan_summary['scan_date']}")
    print(f"  Assets processed: {scan_summary['succeeded']}/{scan_summary['total']}")
    if scan_summary["errors"]:
        print(f"  Errors ({len(scan_summary['errors'])}):")
        for error in scan_summary["errors"]:
            err_type = error.get("type", "error")
            message = error.get("message", error.get("error", ""))
            print(f"    [{error['category']}] {error['asset']} ({err_type}): {message}")
    print()
    print("  Top signals by magnitude:")
    all_sigs: list[tuple] = []
    for category, assets in scan_summary["results"].items():
        for name, data in assets.items():
            score = data.get("signal_score")
            if score is not None:
                all_sigs.append((name, category, score, data.get("signal_label", "")))
    all_sigs.sort(key=lambda item: -abs(item[2]))
    for name, category, score, label in all_sigs[:10]:
        print(f"    {name:<22s} {label:<20s} {score:+.1f}")
    print("=" * 65)


if __name__ == "__main__":
    main()
