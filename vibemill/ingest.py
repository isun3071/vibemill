"""News ingestion. Pulls AP and BBC RSS feeds, dedupes against news_cache,
returns the new items.

Per OPERATIONS.md: 3 attempts per feed with exponential backoff. If both
feeds fail after their attempts, return [] and the caller skips the cron tick.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import feedparser
import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from . import db
from .models import NewsItem

log = logging.getLogger(__name__)

FEEDS: dict[str, str] = {
    # AP retired their public RSS at some point in 2025. NPR substituted as
    # the second feed; keeps two-feed diversity and the geographic balance.
    "npr": "https://feeds.npr.org/1001/rss.xml",
    "bbc": "https://feeds.bbci.co.uk/news/rss.xml",
}

_TIMEOUT_S = 30


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
)
def _fetch(url: str) -> bytes:
    r = httpx.get(url, timeout=_TIMEOUT_S, follow_redirects=True)
    r.raise_for_status()
    return r.content


def _parse_feed(source: str, body: bytes) -> list[NewsItem]:
    parsed = feedparser.parse(body)
    items: list[NewsItem] = []
    for entry in parsed.entries:
        url = getattr(entry, "link", None)
        headline = getattr(entry, "title", None)
        if not url or not headline:
            continue
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "")
        published_at: datetime | None = None
        if struct := getattr(entry, "published_parsed", None):
            try:
                published_at = datetime(*struct[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                published_at = None
        items.append(
            NewsItem(
                url=url,
                headline=headline,
                summary=summary,
                feed_source=source,
                published_at=published_at,
            )
        )
    return items


def fetch_new_items() -> list[NewsItem]:
    """Fetch all configured feeds, drop items already in news_cache,
    return the new ones.

    Failures on a single feed are logged and skipped; a totally empty result
    means the caller should bail this cron tick.
    """
    new_items: list[NewsItem] = []
    for source, url in FEEDS.items():
        try:
            body = _fetch(url)
        except Exception as exc:
            log.warning("ingest: %s feed failed after retries: %s", source, exc)
            continue
        for item in _parse_feed(source, body):
            if db.get_cached_news(item.url) is not None:
                continue
            new_items.append(item)
    log.info("ingest: %d new items across %d feeds", len(new_items), len(FEEDS))
    return new_items
