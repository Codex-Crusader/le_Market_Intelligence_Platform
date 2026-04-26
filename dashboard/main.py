"""
Legacy dashboard entry point.

The canonical path is now:  streamlit run pulseengine/local/dashboard.py

This file re-executes the canonical script so that
`streamlit run dashboard/main.py` continues to work unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

_canonical = Path(__file__).resolve().parents[1] / "pulseengine" / "local" / "dashboard.py"
exec(compile(_canonical.read_text(encoding="utf-8"), str(_canonical), "exec"))  # noqa: S102
