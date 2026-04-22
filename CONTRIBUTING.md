# Contributing to PulseEngine

[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen?style=flat-square)](https://github.com/The-Pulse-Engine/Pulse-Engine_Market_Intelligence_Platform/pulls)
[![Issues](https://img.shields.io/badge/Issues-Open-blue?style=flat-square)](https://github.com/The-Pulse-Engine/Pulse-Engine_Market_Intelligence_Platform/issues)
[![Code Style: PEP8](https://img.shields.io/badge/Code%20Style-PEP%208-4B8BBE?style=flat-square)](https://peps.python.org/pep-0008/)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

Thank you for your interest in contributing. This document explains how to report bugs, propose changes, and submit pull requests.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Reporting Bugs](#reporting-bugs)
- [Proposing Features](#proposing-features)
- [Development Setup](#development-setup)
- [IDE Setup](#ide-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Areas Open for Contribution](#areas-open-for-contribution)
- [What Not to Change](#what-not-to-change)

---

## Code of Conduct

This project follows a standard open-source code of conduct. All contributors are expected to communicate respectfully, provide constructive feedback, and keep discussions focused on the technical content of the project.

---

## How to Contribute

1. Fork the repository on GitHub
2. Create a feature branch from `main`
3. Make your changes with clear, focused commits
4. Open a pull request with a clear description of the change and why it is needed
5. Respond to review comments

For significant changes (new features, architectural changes, changes to the signal model), open an issue first to discuss the approach before writing code.

---

## Reporting Bugs

Open a GitHub issue using the following template:

```
Title: [Bug] Short description of the issue

Environment:
  - OS:
  - Python version:
  - Package versions (pip freeze output or requirements):

Description:
  What happened vs. what was expected.

Steps to reproduce:
  1.
  2.
  3.

Error output or traceback (if any):
  (paste here)

Additional context:
  (screenshots, log files, etc.)
```

Please include the full traceback when reporting runtime errors. Do not open duplicate issues — search existing issues first.

---

## Proposing Features

Open a GitHub issue using the following template:

```
Title: [Feature] Short description of the proposed feature

Problem being solved:
  What limitation or gap does this address?

Proposed solution:
  How would this work? Which files would change?

Alternatives considered:
  What other approaches were considered and why were they rejected?

Additional context:
  Any supporting information, references, or screenshots.
```

---

## Development Setup

```bash
# 1. Fork and clone
git clone https://github.com/The-Pulse-Engine/Pulse-Engine_Market_Intelligence_Platform.git
cd Pulse-Engine_Market_Intelligence_Platform

# 2. Create a virtual environment
# Python 3.11–3.14 are all supported
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 4. Run the test suite
pytest

# 5. Verify the pipeline works
python -m app.scan --dry-run

# 5. Run the dashboard
streamlit run pulseengine/local/dashboard.py
```

---

## IDE Setup

The repository ships pre-configured debug/run configurations for the two most common editors used by open-source Python contributors. Both sets of configs use only portable, project-relative paths so they work on any machine without modification.

### VS Code

Requires the [Python](https://marketplace.visualstudio.com/items?itemName=ms-python.python) and [Debugpy](https://marketplace.visualstudio.com/items?itemName=ms-python.debugpy) extensions.

Open the project folder in VS Code. The configurations in `.vscode/launch.json` will appear in the **Run and Debug** panel (`Ctrl+Shift+D`):

| Configuration | Equivalent command |
|---|---|
| Dashboard (Streamlit) | `streamlit run pulseengine/local/dashboard.py` |
| Scan (Dry Run) | `python -m app.scan --dry-run` |
| Scan (Full) | `python -m app.scan` |
| Analysis CLI | `python -m app.analysis` |
| Tests (pytest) | `pytest tests/ -v --tb=short` |

Select your virtual environment interpreter (`Ctrl+Shift+P` → *Python: Select Interpreter* → choose `.venv`), then pick any configuration and press `F5` to run with debugging.

### PyCharm (Community or Professional)

Open the project root as a PyCharm project. Configure the interpreter once via **File → Settings → Project → Python Interpreter** — point it at `.venv/Scripts/python` (Windows) or `.venv/bin/python` (macOS/Linux).

The run configurations in `.idea/runConfigurations/` are loaded automatically by PyCharm and appear in the run/debug dropdown in the toolbar:

| Configuration | Equivalent command |
|---|---|
| Dashboard | `python -m streamlit run pulseengine/local/dashboard.py` |
| Scan (Dry Run) | `python -m app.scan --dry-run` |
| Scan (Full) | `python -m app.scan` |
| Analysis CLI | `python -m app.analysis` |
| Tests | `pytest tests/ -v --tb=short` |

Select a configuration from the dropdown and press the green **Run** button or **Debug** button (the bug icon) to launch with a full debugger attached.

---

## Code Style

[![PEP 8](https://img.shields.io/badge/style-PEP%208-4B8BBE?style=flat-square)](https://peps.python.org/pep-0008/)

All code must follow PEP 8. Key conventions used in this codebase:

- **Line length**: 99 characters maximum
- **Indentation**: 4 spaces, no tabs
- **Naming**:
  - `snake_case` for functions and variables
  - `UPPER_SNAKE_CASE` for module-level constants in `config/settings.py`
  - `_leading_underscore` for private/internal functions
- **Type hints**: Use type hints on all function signatures. Use `Optional[T]` from `typing` for nullable returns
- **Docstrings**: One-line docstrings for simple functions, multi-line for public functions with multiple parameters or complex return values
- **Imports**: Standard library first, third-party second, local last — each group separated by a blank line
- **No magic numbers**: All tunable values must live in `config/settings.py`, never hardcoded in `app/analysis.py`, `dashboard/main.py`, or elsewhere

### Style Rules Specific to This Project

- Do not add `print()` statements to `app/analysis.py`, `dashboard/main.py`, `storage/storage.py`, `app/backtest.py`, or `app/scan.py`. Use the `logging` module
- Do not use `st.write()` for debug output in `dashboard/main.py`. All debug output belongs in log files
- Exception handling must be specific. Broad `except Exception` clauses are only acceptable at the outermost layer where a crash must be prevented from reaching the user interface (e.g. storage writes inside the dashboard)
- All `@st.cache_data` and `@st.cache_resource` functions must include `ttl` or use the singleton pattern documented in `dashboard/main.py`

---

## Testing

The project has a `pytest` test suite. Install dev dependencies and run it before submitting a pull request:

```bash
pip install -r requirements-dev.txt
pytest
```

All tests should pass. The suite covers:
- Core function invariants (RSI range, signal score range, sentiment range)
- Pipeline smoke tests (`analyse_asset`, `run_full_scan`)
- Edge case coverage for scoring, sentiment, deduplication, and contradictions
- Storage round-trip, retention policy, dry-run scan, and backtest evaluation

The tests are intentionally minimal — they verify the pipeline runs and outputs are sane,
not that every key and value matches exactly. See `tests/MAINTENANCE.md` for guidance on
when and how to update tests.

In addition to the automated tests, verify the following manually before submitting:

1. **Dry run passes without errors**
   ```bash
  python -m app.scan --dry-run
   ```

2. **Dashboard loads without warnings or errors in the terminal**
   ```bash
  streamlit run pulseengine/local/dashboard.py
   ```

3. **At least two assets from different categories render correctly** in the dashboard without errors in the Streamlit UI or the terminal

4. **Storage round-trip works** — after a scan, `market_data/` should contain at least one `.json.gz` file per asset category

5. **No FutureWarnings or DeprecationWarnings** appear in the terminal output

If you are modifying signal scoring logic (`compute_signal_score` in `src/signals.py`), also verify that:
- Signal scores remain within the -10 to +10 range for a representative set of assets
- Signal labels map correctly to the configured thresholds in `config/settings.py`

---

## Pull Request Process

1. **Branch naming**: Use `feature/short-description`, `fix/short-description`, or `docs/short-description`
2. **Commit messages**: Use the imperative mood. Example: `fix pct_change FutureWarning in compute_price_metrics`, not `fixed` or `fixing`
3. **Scope**: One logical change per pull request. Do not bundle unrelated changes
4. **Description**: Explain *what* changed and *why*. Reference the issue number if applicable (`Closes #42`)
5. **config/settings.py changes**: Any new constant added to `config/settings.py` must be documented in the pull request description with its purpose, default value, and acceptable range
6. **Breaking changes**: Label the PR `breaking change` and describe the migration path in the PR description
7. **Do not commit**:
   - `market_data/` contents
   - `.venv/` or any virtual environment directory
   - IDE workspace files beyond the committed configs (`.idea/workspace.xml`, `.idea/*.iml`, `.vscode/settings.json`, etc.)
   - Any file containing API keys, tokens, or credentials

---

## Areas Open for Contribution

The following areas are particularly welcome for contribution:

| Area | Description |
|---|---|
| Additional assets | New tickers can be added to `TRACKED_ASSETS` in `config/settings.py` along with keywords in `ASSET_KEYWORDS` and peers in `SECTOR_PEERS` |
| Additional news feeds | New RSS feeds can be added to `NEWS_FEEDS` in `config/settings.py` with a corresponding entry in `SOURCE_WEIGHTS` |
| Test suite expansion | The current suite is intentionally minimal (14 tests). As the codebase stabilises, contributions that add meaningful invariant or integration tests are welcome — see `tests/MAINTENANCE.md` for what makes a good test here |
| Export functionality | CSV or Excel export of the category overview table |
| Alert system | Email or webhook notification when a signal crosses a configurable threshold |
| Improved deduplication | Replace Jaccard similarity with a more robust semantic deduplication approach |
| Documentation | Improvements to `Docs/code_flow.md` and `Docs/variable_list.md` |

---

## What Not to Change

The following design decisions are intentional and should not be changed without opening an issue for discussion first:

- **All configuration in `config/settings.py`**: Do not hardcode values in any other file
- **`@st.cache_resource` for the scan state singleton**: Changing this to a module-level variable would recreate the lock on every Streamlit rerun
- **`fill_method=None` on `pct_change()`**: This is an explicit fix for a pandas FutureWarning. Do not revert to the default
- **Daemon threads for background scanning**: The scan must not block the dashboard UI thread
- **Tiered storage retention**: The three-tier retention policy (full / reduced / deleted) is intentional to balance disk usage against backtesting depth
