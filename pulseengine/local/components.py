"""Compatibility wrapper for the local dashboard component library."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from dashboard.components import *  # noqa: F401,F403
