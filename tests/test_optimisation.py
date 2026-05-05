"""
test_optimisation.py — Correctness tests for the optimised code paths.

Covers the two checks that failed in the ad-hoc validation scripts:

  1. deduplicate_articles inverted-index equivalence
     The previous ad-hoc test used titles that shared many common tokens
     ("completely unique article number … about topic …"), which correctly
     produced high Jaccard scores and were correctly deduplicated — the test
     expectation was wrong, not the code.  These tests use domain-specific
     vocabularies with minimal overlap.

  2. time.sleep placement relative to _yf_semaphore
     The previous text-parser misread indentation levels and gave a false
     positive.  This test uses the ast module to walk the function's parse
     tree and verify that no time.sleep() call appears inside a
     `with _yf_semaphore:` block.
"""

from __future__ import annotations

import ast
import datetime as dt
import inspect
import textwrap

import pytest

from pulseengine.core.news import deduplicate_articles, _jaccard, _normalize_title
from pulseengine.core.config import DEDUP_SIMILARITY_THRESHOLD


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_article(title: str, hours_old: int = 1) -> dict:
    return {
        "title":     title,
        "summary":   "",
        "link":      "https://example.com",
        "source":    "Test",
        "published": dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours_old),
    }


def _dedup_naive(articles: list[dict]) -> list[dict]:
    """Reference O(n²) implementation — used as ground-truth for equivalence tests."""
    seen: list[set] = []
    deduped: list[dict] = []
    for a in articles:
        tokens = set(_normalize_title(a["title"]).split())
        if not tokens:
            deduped.append(a)
            continue
        if not any(_jaccard(tokens, p) >= DEDUP_SIMILARITY_THRESHOLD for p in seen):
            seen.append(tokens)
            deduped.append(a)
    return deduped


# ── deduplicate_articles — correctness ───────────────────────────────────────

def test_dedup_empty_input():
    assert deduplicate_articles([]) == []


def test_dedup_single_article_kept():
    arts = [_make_article("Gold prices hit record high on central bank demand")]
    assert len(deduplicate_articles(arts)) == 1


def test_dedup_exact_duplicate_kept_once():
    title = "Gold prices hit record high on central bank demand"
    arts = [_make_article(title), _make_article(title)]
    assert len(deduplicate_articles(arts)) == 1


def test_dedup_first_article_wins():
    """When two articles are duplicates the earlier one (index 0) must be kept."""
    a1 = _make_article("Gold surges on safe haven demand today")
    a2 = _make_article("Gold surges on safe haven demand today")
    result = deduplicate_articles([a1, a2])
    assert result[0] is a1


def test_dedup_empty_title_always_kept():
    """Articles with no tokens after normalisation pass through without comparison."""
    arts = [_make_article(""), _make_article(""), _make_article("Real news here")]
    result = deduplicate_articles(arts)
    # Both empty-title articles are kept (no tokens → no comparison)
    assert len(result) == 3


def test_dedup_distinct_domain_vocabularies_all_kept():
    """
    Articles from different domains (equities, crypto, commodities, macro, energy)
    use non-overlapping vocabulary and must all survive deduplication.

    Previous ad-hoc test used titles like 'Completely unique article number N about
    topic N' which shared 6+ tokens, correctly producing Jaccard ≈ 0.67 > threshold.
    These titles are chosen to have minimal cross-domain token overlap.
    """
    articles = [
        _make_article("Apple iPhone quarterly earnings revenue beat expectations"),
        _make_article("Federal Reserve interest rates monetary policy inflation"),
        _make_article("Bitcoin cryptocurrency halving blockchain digital currency"),
        _make_article("Gold bullion precious metals safe haven central bank"),
        _make_article("OPEC crude barrel petroleum supply production cuts"),
        _make_article("Microsoft Azure cloud computing software quarterly results"),
        _make_article("Tesla electric vehicle deliveries energy gigafactory"),
        _make_article("Amazon AWS retail ecommerce revenue logistics"),
        _make_article("Ethereum defi smart contract staking layer upgrade"),
        _make_article("Wheat corn grain agriculture drought harvest"),
    ]
    result = deduplicate_articles(articles)
    assert len(result) == len(articles), (
        f"Expected {len(articles)} articles kept, got {len(result)}. "
        "Check for unexpected token overlap in the test titles."
    )


# ── deduplicate_articles — equivalence with naive O(n²) ──────────────────────

@pytest.mark.parametrize("batch,description", [
    (
        [
            _make_article("Gold surges on Federal Reserve announcement today"),
            _make_article("Gold surges on Fed announcement today"),       # near-dup
            _make_article("Bitcoin drops sharply overnight below support"),
            _make_article("Gold surges on Federal Reserve announcement today"),  # exact dup
            _make_article("Nasdaq recovers losses after tech selloff"),
        ],
        "mixed near-dups and exact dups",
    ),
    (
        [_make_article("Apple earnings"), _make_article("Oil supply shock"), _make_article("VIX spikes")],
        "all unique single-event titles",
    ),
    (
        [_make_article("Gold prices rise today")] * 4,
        "four identical titles",
    ),
    (
        [_make_article("gold"), _make_article("silver"), _make_article("gold")],
        "single-token titles with one duplicate",
    ),
])
def test_dedup_matches_naive_implementation(batch, description):
    """Inverted-index result must be identical to the naive O(n²) reference."""
    result_new   = [a["title"] for a in deduplicate_articles(batch)]
    result_naive = [a["title"] for a in _dedup_naive(batch)]
    assert result_new == result_naive, (
        f"Mismatch on batch '{description}':\n"
        f"  new={result_new}\n  naive={result_naive}"
    )


# ── price.py — time.sleep not inside _yf_semaphore ───────────────────────────

def _sleep_inside_semaphore(func) -> list[int]:
    """
    Parse *func* with ast and return line numbers of any time.sleep() calls
    that appear directly inside a `with _yf_semaphore:` block.

    Uses ast.walk on the With node's body so nesting depth doesn't matter —
    unlike the previous text-based check which misread indentation levels.
    """
    src  = textwrap.dedent(inspect.getsource(func))
    tree = ast.parse(src)
    bad_lines: list[int] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.With):
            continue
        uses_semaphore = any(
            isinstance(item.context_expr, ast.Name)
            and item.context_expr.id == "_yf_semaphore"
            for item in node.items
        )
        if not uses_semaphore:
            continue
        # Walk every node inside this With block's body.
        # Iterate over each statement directly to avoid constructing a
        # synthetic ast.Module wrapper.  Annotated as ast.AST to satisfy
        # the type-checker (ast.stmt is a subclass but PyCharm narrows too far).
        body_node: ast.AST
        for body_node in node.body:
            for child in ast.walk(body_node):
                if not isinstance(child, ast.Call):
                    continue
                fn = child.func
                if (
                    isinstance(fn, ast.Attribute)
                    and fn.attr == "sleep"
                    and isinstance(fn.value, ast.Name)
                    and fn.value.id == "time"
                ):
                    bad_lines.append(child.lineno)

    return bad_lines


def test_fetch_price_history_sleep_outside_semaphore():
    """time.sleep must not be called while holding the yfinance semaphore."""
    from pulseengine.core.price import fetch_price_history
    bad = _sleep_inside_semaphore(fetch_price_history)
    assert not bad, (
        f"fetch_price_history: time.sleep() found inside _yf_semaphore at line(s) {bad}. "
        "This blocks all PRICE_FETCH_WORKERS slots during the delay."
    )


def test_fetch_via_ticker_history_sleep_outside_semaphore():
    """Same invariant for the Ticker.history() fallback fetcher."""
    from pulseengine.core.price import _fetch_via_ticker_history
    bad = _sleep_inside_semaphore(_fetch_via_ticker_history)
    assert not bad, (
        f"_fetch_via_ticker_history: time.sleep() found inside _yf_semaphore at line(s) {bad}."
    )
