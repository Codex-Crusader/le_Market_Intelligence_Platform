# PulseEngine Roadmap

[![Status: Active](https://img.shields.io/badge/Status-Active%20Development-22c55e?style=flat-square)]()
[![Vision: Local First](https://img.shields.io/badge/Vision-Local%20First-0ea5e9?style=flat-square)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](../LICENSE)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square)](../CONTRIBUTING.md)
[![Disclaimer](https://img.shields.io/badge/Disclaimer-Not%20Financial%20Advice-red?style=flat-square)](DISCLAIMER.md)

This document exists so contributors can see where PulseEngine is going, pick a lane, and build something that matters.

The project is split into two surfaces sharing one core engine:

- **Local app** — the full product. Runs entirely on your machine. No cloud, no accounts, no data leaving your device. This is the priority.
- **Web demo** — a restricted live preview hosted on Streamlit Community Cloud. Drives awareness and downloads. Not the end goal.

---

## Table of Contents

- [Current State](#current-state)
- [v0.3 Foundation Split](#v03--foundation-split--arbitrary-tickers)
- [v0.4 Desktop Experience](#v04--desktop-experience)
- [v0.5 Local Intelligence](#v05--local-intelligence)
- [v1.0 Full Market](#v10--full-market-coverage)
- [Web Demo Track](#web-demo-track)
- [Out of Scope](#out-of-scope)
- [Contributing to the Roadmap](#contributing-to-the-roadmap)

---

## Current State

[![Version](https://img.shields.io/badge/Version-0.3.0-a16207?style=flat-square)]()
[![Assets](https://img.shields.io/badge/Assets-24%20Tracked-0ea5e9?style=flat-square)]()
[![Tests](https://img.shields.io/badge/Tests-54%20passing-22c55e?style=flat-square)]()
[![Sentiment](https://img.shields.io/badge/Sentiment-VADER-7c3aed?style=flat-square)]()
[![Demo](https://img.shields.io/badge/Demo-Live-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://pulseengine.streamlit.app/)

What exists right now:

- 24 tracked assets across Commodities, Cryptocurrency, Tech Stocks, and Market Indices
- Arbitrary ticker lookup — enter any valid Yahoo Finance symbol in the sidebar
- VADER sentiment engine with injected financial lexicon
- 12 RSS feeds ingested in parallel with Jaccard deduplication
- RSI, momentum, trend strength, and 8-category event detection
- Per-asset-class signal weighting profiles
- Background scan daemon refreshing all assets every 30 minutes
- Compressed snapshot storage with tiered retention (7 / 30 / 60 days)
- Backtesting module with hit-rate evaluation
- Streamlit live demo at [pulseengine.streamlit.app](https://pulseengine.streamlit.app/)
- Docker support, 54 tests, full documentation
- Local installer (`install.py`, `install.sh`, `install.ps1`) with zero terminal friction
- Clean `pulseengine/core/` + `pulseengine/local/` + `pulseengine/web/` split — completed in v0.3.0

What is missing:

- A desktop executable
- A proper financial NLP model

---

## v0.3 — Foundation Split + Arbitrary Tickers

[![Priority](https://img.shields.io/badge/Priority-Critical%20Path-ef4444?style=flat-square)]()
[![Track](https://img.shields.io/badge/Track-Shared-6b7280?style=flat-square)]()
[![Contributor Friendly](https://img.shields.io/badge/Contributors-Welcome-22c55e?style=flat-square)]()

> Everything after this milestone depends on it. Do not skip ahead.

### Repo restructure

> **Done in v0.3.0.** The codebase is now split into `pulseengine/core/` (shared engine), `pulseengine/local/` (full-featured local app), and `pulseengine/web/` (restricted stateless demo). Old flat packages (`app/`, `dashboard/`, `src/`, `config/`, `storage/`) remain as backward-compat shims and do not need modification.

### Arbitrary ticker support

> **Done in v0.3.0.** Users can enter any valid Yahoo Finance ticker in the dashboard sidebar. `generate_keywords` in `pulseengine.core.news` auto-builds keyword coverage from ticker metadata; the dashboard applies low-news-confidence safeguards when coverage is sparse.

### Other v0.3 deliverables

> **All done in v0.3.0.**
- Local installer (`install.py`, `install.sh`, `install.ps1`) — one command, no friction, generates platform launch scripts
- `ROADMAP.md` published and linked from the README

---

## v0.4 — Desktop Experience

[![Track](https://img.shields.io/badge/Track-Local%20App-0ea5e9?style=flat-square)]()
[![Target](https://img.shields.io/badge/Target-Windows%20%7C%20macOS%20%7C%20Linux-3776AB?style=flat-square)]()
[![Build](https://img.shields.io/badge/Build-PyInstaller-f59e0b?style=flat-square)]()

The goal: download and double-click. No terminal required.

| Deliverable | Detail |
|---|---|
| PyInstaller EXE | Windows first, then macOS and Linux |
| Launcher script | Starts the server, waits for ready, opens browser automatically |
| System tray icon | Shows running status, allows clean shutdown |
| GitHub Actions pipeline | Builds and attaches platform binaries to every release tag |
| First-run setup | Lightweight wizard to configure data directory on first launch |

---

## v0.5 — Local Intelligence

[![Track](https://img.shields.io/badge/Track-Local%20App-0ea5e9?style=flat-square)]()
[![NLP](https://img.shields.io/badge/NLP-FinBERT-7c3aed?style=flat-square)]()
[![Offline](https://img.shields.io/badge/Mode-Offline%20Capable-22c55e?style=flat-square)]()

This is where the local app becomes genuinely independent of any external service.

| Deliverable | Detail |
|---|---|
| FinBERT local model | Downloaded once on first run, cached permanently, runs fully offline |
| Offline mode | Serve cached data when network unavailable, flag signal staleness clearly |
| Export | CSV and PDF export of signal reports and backtest results |
| Backtest improvements | Lag correction, rolling validation, signal weight evaluation |
| Test coverage | Property-based tests for pure functions, integration tests for full pipeline |
| Custom RSS feeds | Users add their own news sources via config |

---

## v1.0 — Full Market Coverage

[![Track](https://img.shields.io/badge/Track-Shared-6b7280?style=flat-square)]()
[![Scope](https://img.shields.io/badge/Scope-All%20Stocks-a16207?style=flat-square)]()
[![Community](https://img.shields.io/badge/Driven%20By-Community-7c3aed?style=flat-square)]()

> Timeline depends on community growth. The more contributors, the faster this lands.

| Deliverable | Detail |
|---|---|
| Dynamic asset discovery | System finds and covers stocks automatically |
| All stocks | Any exchange, any ticker, any news volume |
| Auto-generated company profiles | Executive names, subsidiaries, products — all derived automatically |
| News routing at scale | RSS feeds alone will not cut it at this volume |
| Signal weight auto-tuning | Weights validated against rolling historical data, not hand-tuned |
| Alert system | Local desktop notification when a signal crosses a configurable threshold |
| Community sector profiles | Contributors own their domain and maintain keyword profiles for their sectors |

---

## Web Demo Track

[![Status](https://img.shields.io/badge/Status-Live-22c55e?style=flat-square)]()
[![Features](https://img.shields.io/badge/Features-Restricted-f59e0b?style=flat-square)]()
[![Purpose](https://img.shields.io/badge/Purpose-Drive%20Downloads-0ea5e9?style=flat-square)]()
[![Storage](https://img.shields.io/badge/Storage-None.%20Ever.-22c55e?style=flat-square)]()

The web demo is not a separate project. It runs off the same core engine and stays deliberately limited. Its only job is to give people a taste of the tool and send them to the local download.

| Feature | Local App | Web Demo |
|---|---|---|
| All 24 current assets | Yes | Yes |
| Arbitrary ticker lookup | Yes | No |
| Backtesting | Yes | No |
| Historical snapshots | Yes | No |
| FinBERT local model | Yes | No |
| Custom RSS feeds | Yes | No |
| Export to CSV / PDF | Yes | No |
| Offline mode | Yes | No |
| Data stored anywhere | Never | Never |

> **Privacy commitment:** We store nothing. Ever. The web demo is architecturally incapable of retaining user data.

---

### Repo structure at v1.0
```
pulseengine/
  core/
    app.py                  Core analysis engine
    config.py               All configuration constants
    storage.py              Snapshot persistence and retention
    backtest.py             Historical signal accuracy evaluation
  local/
    dashboard.py            Full Streamlit dashboard
    scan.py                 Full-market batch scan pipeline
    launcher.py             EXE launcher, tray icon, browser open
    setup.py                First-run installer wizard
  web/
    dashboard.py            Restricted Streamlit demo
    api/                    FastAPI layer (future)
  Docs/
    ROADMAP.md              This file
    CHANGELOG.md            Version history
    DISCLAIMER.md           Legal and financial disclaimer
    code_flow.md            Execution flow diagrams
    variable_list.md        Variable and constant reference
  tests/
    conftest.py             Shared fixtures
    test_core.py            Pure function unit tests
    test_pipeline.py        End-to-end pipeline smoke tests
    MAINTENANCE.md          Guide for updating the test suite
  builds/                   Platform binaries (git-ignored)
  market_data/              Runtime snapshot directory (git-ignored)
  requirements.txt          Production dependencies
  requirements-dev.txt      Test dependencies
  Dockerfile                Container build
  README.md                 Project entry point
```
---
## What the Web Demo Unlocks vs Locks

| Feature | Web Demo | Local App |
|---|---|---|
| assets | Yes | Yes |
| Signal score + explanation | Yes | Yes |
| Price chart | Yes | Yes |
| News sentiment feed | Yes | Yes |
| Market heatmap | Yes | Yes |
| Arbitrary ticker lookup | No | Yes |
| Backtesting | No | Yes |
| Historical snapshots | No | Yes |
| Export to CSV / PDF | No | Yes |
| FinBERT local model | No | Yes |
| Custom RSS feeds | No | Yes |
| Offline mode | No | Yes |

> Locked features in the web demo display a prompt to download the local app. No feature is paywalled. No feature requires an account. The local app is free forever.

---

## Out of Scope

[![Not This](https://img.shields.io/badge/Not%20This-Trading%20Platform-ef4444?style=flat-square)]()
[![Not This](https://img.shields.io/badge/Not%20This-SaaS%20Product-ef4444?style=flat-square)]()
[![Not This](https://img.shields.io/badge/Not%20This-Paid%20Tool-ef4444?style=flat-square)]()
[![Not This](https://img.shields.io/badge/Not%20This-Data%20Vendor-ef4444?style=flat-square)]()

These are things PulseEngine will not become:

- **A trading platform.** No order execution, no brokerage integration, no portfolio management.
- **A SaaS product.** No user accounts, no subscriptions, no cloud lock-in.
- **A paid tool.** Free forever, MIT licensed.
- **A data vendor.** All data sourced from free public feeds. No proprietary data.

---

## Contributing to the Roadmap

The issue tracker is the best place to start. Issues are tagged by difficulty and area:

[![Label](https://img.shields.io/badge/-good%20first%20issue-7057ff?style=flat-square)]()
Self-contained, no domain knowledge required.

[![Label](https://img.shields.io/badge/-backend-0075ca?style=flat-square)]()
Core engine, data pipeline, storage.

[![Label](https://img.shields.io/badge/-frontend-e4e669?style=flat-square)]()
Dashboard UI, Streamlit components.

[![Label](https://img.shields.io/badge/-docs-0075ca?style=flat-square)]()
Documentation, examples, guides.

[![Label](https://img.shields.io/badge/-medium-e4e669?style=flat-square)]()
Meaningful scope, some codebase familiarity needed.

If you want to work on something not in the issue tracker, open an issue first and describe what you are planning. This avoids duplicate work and makes sure your contribution fits the direction.

Read [CONTRIBUTING.md](../CONTRIBUTING.md) before opening a pull request.

---

### Architecture note for contributors

The `core/` directory is the shared foundation. Changes there affect both the local app and the web demo. Keep it clean, well-tested, and free of surface-specific logic.

The `local/` directory can be heavy. FinBERT, backtesting, snapshot storage, export. No apologies for size or compute requirements here.

The `web/` directory must stay lightweight. No local model inference, no file I/O, no state between requests. If a feature cannot run statelessly in a browser session, it belongs in `local/` only.

---

*PulseEngine is MIT licensed. See [LICENSE](../LICENSE) for the full text.*
*This is not financial advice. See [DISCLAIMER.md](DISCLAIMER.md) for the full disclaimer.*
