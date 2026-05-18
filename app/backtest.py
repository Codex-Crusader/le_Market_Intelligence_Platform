"""
app/backtest.py — Backward-compatible re-export shim.

All backtesting logic now lives in pulseengine.core/backtest.py.
New code should import directly from pulseengine.core.
"""

from __future__ import annotations

from pulseengine.core.backtest import (  # noqa: F401
    evaluate_all_assets,
    evaluate_signal_accuracy,
    get_signal_streak,
)
