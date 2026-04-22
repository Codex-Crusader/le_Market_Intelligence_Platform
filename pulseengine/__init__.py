"""
PulseEngine — Market Intelligence Platform

A comprehensive system for real-time market analysis combining price data,
news feeds, sentiment analysis, and multi-factor signal generation.

Architectural layers:
    core       - Headless engine module (shared by local/ and web/)
    local      - Full-featured Streamlit dashboard and batch scan CLI
    web        - Restricted Streamlit demo (no file I/O, no local model inference)
"""

__version__ = "0.3.0"
