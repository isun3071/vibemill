"""Tavily web search client.

Single function: search(query, max_results) -> list[SearchResult].

Tavily's REST API: POST https://api.tavily.com/search with body containing
the api_key, query, max_results, and search_depth. Free tier covers 1000
searches/month; pricing above is ~$0.005/search.

Per-query timeout is enforced; on timeout or any other error the function
returns an empty list (graceful degradation — search is enriching, not
required).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from ..config import get_settings

log = logging.getLogger(__name__)

API_URL = "https://api.tavily.com/search"
QUERY_TIMEOUT_S = 10
ESTIMATED_COST_PER_QUERY_USD = 0.005


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class TavilyError(RuntimeError):
    pass


def search(query: str, *, max_results: int = 5) -> list[SearchResult]:
    """One Tavily search. Returns parsed results, or empty list on any
    failure (no API key configured, network error, non-2xx, parse error,
    timeout). Failures log a warning."""
    s = get_settings()
    key = s.WEB_SEARCH_API_KEY.get_secret_value()
    if not key:
        log.warning("tavily: WEB_SEARCH_API_KEY not configured; returning no results")
        return []

    payload = {
        "api_key": key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
    }
    try:
        r = httpx.post(API_URL, json=payload, timeout=QUERY_TIMEOUT_S)
    except httpx.TimeoutException:
        log.warning("tavily: query timeout (%ds): %r", QUERY_TIMEOUT_S, query[:80])
        return []
    except httpx.TransportError as exc:
        log.warning("tavily: transport error: %s", exc)
        return []

    if r.status_code != 200:
        log.warning("tavily: HTTP %d for %r: %s", r.status_code, query[:80], r.text[:200])
        return []

    try:
        body = r.json()
    except ValueError:
        log.warning("tavily: non-JSON response for %r", query[:80])
        return []

    results: list[SearchResult] = []
    for entry in body.get("results", []):
        title = entry.get("title") or ""
        url = entry.get("url") or ""
        # Tavily uses "content" for the snippet text.
        snippet = entry.get("content") or ""
        if title and url:
            results.append(SearchResult(title=title, url=url, snippet=snippet))
    log.info("tavily: %d results for %r (%.0f ms)", len(results), query[:60],
             body.get("response_time", 0) * 1000 if isinstance(body.get("response_time"), (int, float)) else 0)
    return results
