"""
pulseengine.web — Restricted Streamlit demo surface.

Architectural constraints:
  - No file I/O (no disk reads or writes)
  - No local model inference (no FinBERT)
  - No persistent state between requests
  - No arbitrary ticker lookup
  - No backtesting
  - No historical snapshots

This surface is deployed to Streamlit Community Cloud. Its only job is to
give users a live taste of the tool and direct them to the local download.

Entry point:
    streamlit run pulseengine/web/dashboard.py
"""
