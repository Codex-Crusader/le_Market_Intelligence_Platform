"""Regression tests for the restricted PulseEngine web surface."""

from __future__ import annotations

import ast
from pathlib import Path


WEB_DASHBOARD = Path(__file__).resolve().parents[1] / "pulseengine" / "web" / "dashboard.py"
WEB_INIT = Path(__file__).resolve().parents[1] / "pulseengine" / "web" / "__init__.py"


def test_web_surface_stays_on_core_only() -> None:
    """The web demo must not import from pulseengine.local."""
    source = WEB_DASHBOARD.read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert WEB_INIT.exists()
    assert "Download the local app" in source
    assert "We store nothing. Ever." in source

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("pulseengine.local")


def test_web_surface_documents_locked_features() -> None:
    """The web demo should clearly call out local-only features."""
    source = WEB_DASHBOARD.read_text(encoding="utf-8")

    for feature in (
        "Arbitrary ticker lookup",
        "Backtesting",
        "Historical snapshots",
        "Export to CSV / PDF",
        "FinBERT local model",
        "Custom RSS feeds",
        "Offline mode",
    ):
        assert feature in source