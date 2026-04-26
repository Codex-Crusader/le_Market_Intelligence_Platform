"""Backward-compat shim. Real code lives in pulseengine/local/data.py."""
from pulseengine.local.data import *  # noqa: F401,F403
from pulseengine.local.data import (  # noqa: F401
    cached_news,
    cached_generated_keywords,
    cached_history,
    cached_live_analysis,
    cached_scan_summary,
    is_data_stale,
)
