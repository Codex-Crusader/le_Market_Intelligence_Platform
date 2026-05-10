"""
src/news.py — News fetching, deduplication, and clustering.

Single responsibility: acquire and pre-process raw article data from RSS feeds.

Pipeline role (steps 2 and 2.5 of the full engine):
  - fetch_news_articles   : pull recent articles from all configured RSS feeds in parallel
  - deduplicate_articles  : remove near-duplicates via Jaccard title similarity
  - cluster_articles      : group articles by dominant detected event type
  - get_display_clusters  : filtered, summarised cluster view for UI consumption
  - generate_keywords     : auto-build a keyword list for any ticker from Yahoo Finance metadata

This module does NOT score sentiment or match articles to assets — those
responsibilities belong to src/sentiment.py and src/signals.py respectively.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

import feedparser
import yfinance as yf

from .config import (
    DEDUP_SIMILARITY_THRESHOLD,
    MAX_WORKERS,
    NEWS_FEEDS,
    NEWS_MAX_AGE_HOURS,
    NEWS_MAX_ARTICLES,
    RELEVANCE_MEDIUM,
    REQUEST_TIMEOUT,
)

log = logging.getLogger(__name__)

_RE_STRIP_HTML     = re.compile(r"<[^>]+>")
_RE_NORMALIZE_TITLE = re.compile(r"[^a-z0-9\s]")


# ── Fetching ─────────────────────────────────────────────────────────────────

def fetch_news_articles() -> list[dict]:
    """
    Pull recent articles from every configured RSS feed in parallel,
    then deduplicate the combined result.
    """
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=NEWS_MAX_AGE_HOURS)

    def _fetch_feed(source_name: str, feed_url: str) -> list[dict]:
        # Validate URL scheme — only http/https permitted (blocks file://, ftp://, internal addrs)
        try:
            _scheme = urlparse(feed_url).scheme
            if _scheme not in ("http", "https"):
                log.warning("RSS feed %s rejected: unsupported scheme %r", source_name, _scheme)
                return []
        except Exception as _url_exc:
            log.warning("RSS feed %s rejected: invalid URL — %s", source_name, _url_exc)
            return []

        feed_articles: list[dict] = []
        try:
            request = urllib.request.Request(
                feed_url,
                headers={"User-Agent": "PulseEngine/1.0"},
            )
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
                feed = feedparser.parse(response.read())
            for entry in feed.entries:
                pub = _parse_pub_date(entry)
                if pub and pub < cutoff:
                    continue
                # Cap title length to prevent memory exhaustion from malformed feeds
                title   = entry.get("title", "").strip()[:500]
                summary = _strip_html(entry.get("summary", ""))
                if not title:
                    continue
                feed_articles.append({
                    "title":     title,
                    "summary":   summary,
                    "link":      entry.get("link", ""),
                    "source":    source_name,
                    "published": pub,
                })
        except Exception as exc:
            log.warning("RSS error (%s): %s", source_name, str(exc)[:200])
        return feed_articles

    articles: list[dict] = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(_fetch_feed, name, url): name
            for name, url in NEWS_FEEDS
        }
        for future in as_completed(futures):
            articles.extend(future.result())

    articles.sort(
        key=lambda a: a["published"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc),
        reverse=True,
    )
    articles = articles[:NEWS_MAX_ARTICLES]

    before = len(articles)
    articles = deduplicate_articles(articles)
    log.info(
        "Fetched %d articles from %d feeds (%d removed as duplicates)",
        len(articles), len(NEWS_FEEDS), before - len(articles),
    )
    return articles


# ── Deduplication ─────────────────────────────────────────────────────────────

def deduplicate_articles(articles: list[dict]) -> list[dict]:
    """
    Remove near-duplicate articles using Jaccard similarity on title tokens.

    When two titles exceed the similarity threshold, the one that appears
    earlier in the list (higher relevance / more recent) is kept.

    Uses an inverted token index so only articles sharing at least one token
    are compared (Jaccard >= threshold requires a non-empty intersection),
    reducing the worst-case from O(n²) to O(n × avg_overlap).
    """
    # token → list of previously accepted token-sets that contain that token
    inverted_index: dict[str, list[set]] = {}
    deduped: list[dict] = []

    for article in articles:
        tokens = set(_normalize_title(article["title"]).split())
        if not tokens:
            deduped.append(article)
            continue

        # Collect candidate sets that share ≥1 token with the current article.
        # Using id() for O(1) identity-based deduplication avoids comparing the
        # same set object twice when it appears under multiple shared tokens.
        seen_ids: set[int] = set()
        candidates: list[set] = []
        for token in tokens:
            for prev_set in inverted_index.get(token, ()):
                sid = id(prev_set)
                if sid not in seen_ids:
                    seen_ids.add(sid)
                    candidates.append(prev_set)

        is_dup = any(
            _jaccard(tokens, prev) >= DEDUP_SIMILARITY_THRESHOLD
            for prev in candidates
        )
        if not is_dup:
            deduped.append(article)
            for token in tokens:
                inverted_index.setdefault(token, []).append(tokens)

    return deduped


# ── Clustering ────────────────────────────────────────────────────────────────

def cluster_articles(articles: list[dict]) -> dict[str, list[dict]]:
    """
    Group matched articles into topic clusters by dominant event type.

    Articles with no detected event go into the "General News" cluster.
    Clusters are returned sorted by descending size.
    """
    clusters: dict[str, list[dict]] = {}
    for article in articles:
        events = article.get("events_detected", [])
        key    = events[0]["label"] if events else "General News"
        clusters.setdefault(key, []).append(article)

    return dict(sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True))


def get_display_clusters(
    news: list[dict],
    max_clusters: int = 2,
    min_relevance: float | None = None,
) -> dict:
    """
    Return top N topic clusters for display, filtering low-relevance noise.

    Each cluster entry contains:
      label             — topic name (e.g. "Central Bank Policy")
      articles          — filtered article list
      count             — number of articles in cluster
      avg_sentiment     — average compound sentiment score
      sentiment_summary — human-readable summary (e.g. "mostly positive (+0.23)")

    Also returns:
      suppressed_count — articles filtered below min_relevance
      total_shown      — articles remaining after filter
    """
    cutoff = min_relevance if min_relevance is not None else float(RELEVANCE_MEDIUM)

    shown      = [a for a in news if a.get("relevance_score", 0) >= cutoff]
    suppressed = len(news) - len(shown)

    if not shown:
        return {"clusters": [], "suppressed_count": suppressed, "total_shown": 0}

    raw_clusters = cluster_articles(shown)

    clusters_out: list[dict] = []
    for label, articles in list(raw_clusters.items())[:max_clusters]:
        compounds = [a.get("sentiment", {}).get("compound", 0.0) for a in articles]
        avg_sent  = sum(compounds) / len(compounds) if compounds else 0.0

        if avg_sent > 0.15:
            sent_word = "mostly positive"
        elif avg_sent < -0.15:
            sent_word = "mostly negative"
        elif avg_sent > 0.05:
            sent_word = "slightly positive"
        elif avg_sent < -0.05:
            sent_word = "slightly negative"
        else:
            sent_word = "neutral"

        clusters_out.append({
            "label":             label,
            "articles":          articles,
            "count":             len(articles),
            "avg_sentiment":     round(avg_sent, 3),
            "sentiment_summary": f"{sent_word} ({avg_sent:+.2f})",
        })

    return {
        "clusters":        clusters_out,
        "suppressed_count": suppressed,
        "total_shown":     len(shown),
    }


# ── Keyword generation ────────────────────────────────────────────────────────

_CORP_SUFFIXES: frozenset[str] = frozenset({
    "inc", "corp", "corporation", "ltd", "limited", "plc", "llc", "lp",
    "group", "holdings", "co", "company", "technologies", "technology",
    "systems", "services", "solutions", "international", "global",
})


def generate_keywords(ticker: str) -> list[str]:
    """
    Build a keyword list for news correlation from Yahoo Finance metadata.
    Returns a deduplicated list of relevant search terms for the given ticker.
    Falls back to [ticker] if metadata fetch fails.
    """
    ticker = ticker.upper().strip()

    _result: list = [None]
    _exc: list = [None]

    def _fetch() -> None:
        try:
            _result[0] = yf.Ticker(ticker).info
        except Exception as exc:
            _exc[0] = exc

    thread = threading.Thread(target=_fetch, daemon=True)
    thread.start()
    thread.join(timeout=REQUEST_TIMEOUT)

    if thread.is_alive():
        # Thread is abandoned — yfinance is still running in the background.
        # Log at error level so repeated timeouts are visible in monitoring.
        log.error(
            "generate_keywords(%r): metadata fetch timed out after %ds — "
            "daemon thread left running; consider reducing REQUEST_TIMEOUT",
            ticker, REQUEST_TIMEOUT,
        )
        _result[0] = None  # discard any partial result the thread may write later
        return [ticker]

    if _exc[0] is not None:
        log.warning("generate_keywords(%r) failed: %s", ticker, _exc[0])
        return [ticker]

    info = _result[0]

    if not info or not info.get("longName"):
        return [ticker]

    candidates: list[str] = [ticker]

    for field in ("longName", "shortName"):
        val = (info.get(field) or "").strip()
        if not val:
            continue
        candidates.append(val)
        for token in re.split(r"[\s,./&]+", val):
            clean = re.sub(r"[^a-zA-Z0-9]", "", token)
            if clean and clean.lower() not in _CORP_SUFFIXES:
                candidates.append(clean)

    for officer in (info.get("companyOfficers") or [])[:5]:
        name = (officer.get("name") or "").strip()
        if not name:
            continue
        parts = name.split()
        if parts:
            surname = re.sub(r"[^a-zA-Z]", "", parts[-1])
            if surname:
                candidates.append(surname)

    seen: set[str] = set()
    result: list[str] = []
    for kw in candidates:
        kw = kw.strip()
        key = kw.lower()
        if len(kw) >= 3 and key not in seen:
            seen.add(key)
            result.append(kw)

    return result if result else [ticker]


# ── Private helpers ───────────────────────────────────────────────────────────

def _parse_pub_date(entry) -> dt.datetime | None:
    for attr in ("published_parsed", "updated_parsed"):
        parsed = getattr(entry, attr, None)
        if parsed:
            # feedparser guarantees a time.struct_time (9-tuple), but malformed feeds can
            # return other types — validate before unpacking to avoid silent wrong results
            if not isinstance(parsed, (tuple, list)) or len(parsed) < 6:
                continue
            try:
                return dt.datetime(
                    parsed[0], parsed[1], parsed[2],
                    parsed[3], parsed[4], parsed[5],
                    tzinfo=dt.timezone.utc,
                )
            except (ValueError, OverflowError, TypeError):
                pass
    return None


def _strip_html(raw: str) -> str:
    return _RE_STRIP_HTML.sub("", raw).strip()[:600]


def _normalize_title(text: str) -> str:
    return _RE_NORMALIZE_TITLE.sub("", text.lower())


def _jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
