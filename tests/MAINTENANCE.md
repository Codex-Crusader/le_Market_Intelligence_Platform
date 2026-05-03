# Test Suite Maintenance Guide

The test suite is intentionally pragmatic. Its job is to be a **safety net, not a straitjacket**:
catch crashes, broken invariants, and pipeline regressions without freezing internal implementation details.

---

## File Layout

| File | Purpose |
|---|---|
| `conftest.py` | Shared fixtures (price series, DataFrames, articles, signal dicts, mocks) |
| `test_core.py` | Core sanity/invariant tests for pure functions |
| `test_pipeline.py` | Smoke tests for end-to-end orchestration |
| `test_logic_coverage.py` | Additional edge coverage for scoring, sentiment, dedup, contradictions |
| `test_storage_and_scan.py` | Storage retention/cleanup, round-trip, dry-run scan, synthetic backtest |
| `test_optimisation.py` | Optimisation-related tests |
| `test_web_surface.py` | Web demo surface tests |

The suite is no longer fixed to a tiny count. Add tests when they improve confidence on important logic.

---

## What each test file covers

### `test_core.py` and `test_logic_coverage.py`
Pure logic tests. These should verify either:
- The function runs without crashing, or
- A hard invariant/range, or
- A stable business rule (for example clamping, dedup threshold behavior, or contradiction detection).

Prefer robust assertions over fragile full-structure snapshots.

### `test_pipeline.py` and `test_storage_and_scan.py`
Integration/smoke coverage for:
- `analyse_asset()` and `run_full_scan()` with network mocked,
- `run_scan(dry_run=True)` execution,
- storage read/write/retention behaviors,
- synthetic backtest evaluation.

These tests should avoid enforcing unstable presentation details, but they should assert
meaningful pipeline outcomes (no crash, sane outputs, expected side effects).

---

## Import paths

Canonical imports use the `pulseengine.*` package. The existing test files import from the backward-compat shims intentionally — this verifies the shims themselves remain functional. New tests should prefer canonical paths.

| Import style | Module resolved |
|---|---|
| `from pulseengine.core.app import X` | Canonical — `pulseengine/core/app.py` |
| `from pulseengine.core.storage import X` | Canonical — `pulseengine/core/storage.py` |
| `from pulseengine.local.scan import X` | Canonical — `pulseengine/local/scan.py` |
| `from app.analysis import X` | Shim — re-exports from `pulseengine.core` |
| `from storage.storage import X` | Shim — re-exports from `pulseengine.core.storage` |
| `from src.engine import X` | Shim — re-exports from `pulseengine.core.app` |

`conftest.py` imports `storage.storage as storage` so that `monkeypatch.setattr` targets the correct module object.

Network calls are mocked at the point of use in `src/engine.py` (the backward-compat shim). When writing new tests against canonical modules, patch at the canonical location:
- `"pulseengine.core.app.fetch_price_history"`
- `"pulseengine.core.app.fetch_news_articles"`
- `"pulseengine.core.app.analyse_market_context"`

---

## When to update tests

| Change | Action required |
|---|---|
| New key added to `analyse_asset()` result | Usually nothing; avoid strict key snapshots |
| `analyse_asset()` top-level contract changed | Update smoke expectations in `test_pipeline.py` |
| RSI/ROC formula replaced | Re-check range/sign invariants and edge-case behavior |
| Signal score clamping removed | Clamping tests should fail intentionally |
| Dedup threshold changed | Review boundary tests in `test_logic_coverage.py` |
| Storage retention windows changed | Review age-based tests in `test_storage_and_scan.py` |
| Functions moved between `pulseengine/core/` modules | Update patch targets and imports accordingly |

---

## Adding a new test

Before adding a test, ask:
- **Does it protect against a real regression risk?** Good.
- **Does it verify an invariant, edge case, or side effect that matters?** Good.
- **Is it brittle to harmless refactors?** If yes, simplify it.

---

## Running the tests

```bash
# Standard run
pytest

# Single file
pytest tests/test_core.py -v

# With full traceback
pytest --tb=long
```
