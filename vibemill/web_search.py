"""Web search facade: tier-aware query construction + provider dispatch.

Per-tier behavior (see tiers.py):
- SLOP: no search.
- MEAN_GOOD: one search using the news headline.
- BANGER: up to three queries (headline, headline + "data", headline + "timeline")
  to triangulate.

Provider is selected by WEB_SEARCH_PROVIDER (default 'tavily'). Adding
another provider is a single new module under clients/ and one branch in
_dispatch().

Per-app aggregate is returned: combined SearchResult list + count + cost,
suitable for persisting to apps.web_searched / apps.search_queries_count /
apps.search_total_cost.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from . import db
from .clients import tavily
from .clients.tavily import SearchResult
from .config import get_settings
from .models import LlmCall
from .tiers import TierConfig

log = logging.getLogger(__name__)


@dataclass
class SearchOutcome:
    results: list[SearchResult]
    queries_count: int
    cost_usd: float


def _dispatch(query: str, *, max_results: int) -> tuple[list[SearchResult], float]:
    """Run one search via the configured provider. Returns (results, cost)."""
    provider = get_settings().WEB_SEARCH_PROVIDER.lower()
    if provider == "tavily":
        results = tavily.search(query, max_results=max_results)
        return results, tavily.ESTIMATED_COST_PER_QUERY_USD if results else 0.0
    log.warning("web_search: unknown provider %r; returning empty", provider)
    return [], 0.0


def _build_queries(headline: str, summary: str, max_queries: int) -> list[str]:
    """Build up to max_queries search strings. Strategy:
    - Always include the headline.
    - If max_queries >= 2, also try "<headline> data".
    - If max_queries >= 3, also try "<headline> timeline".
    - Beyond 3, repeat with "<topic> statistics" and "<topic> latest" using
      a topic extracted from the headline (rough: first 6 words).
    """
    if max_queries <= 0 or not headline.strip():
        return []
    queries: list[str] = [headline.strip()]
    if max_queries >= 2:
        queries.append(f"{headline.strip()} data")
    if max_queries >= 3:
        queries.append(f"{headline.strip()} timeline")
    if max_queries >= 4:
        topic = " ".join(headline.split()[:6])
        queries.append(f"{topic} statistics")
    if max_queries >= 5:
        topic = " ".join(headline.split()[:6])
        queries.append(f"{topic} latest")
    if max_queries >= 6:
        # Use the summary's first sentence as a sixth angle.
        first = summary.split(".")[0].strip()[:120]
        if first:
            queries.append(first)
    return queries[:max_queries]


def run(*, headline: str, summary: str, tier_cfg: TierConfig, app_id: str | None = None) -> SearchOutcome:
    """Execute the per-tier search plan. Returns aggregated results + cost.
    Each query records one row in llm_calls (purpose='search') so the
    daily cost cap includes search costs. Empty SearchOutcome when tier
    doesn't search or when all queries fail."""
    if not tier_cfg.do_search:
        return SearchOutcome(results=[], queries_count=0, cost_usd=0.0)

    cap = min(tier_cfg.max_search_queries, get_settings().WEB_SEARCH_MAX_QUERIES)
    queries = _build_queries(headline, summary, cap)
    provider = get_settings().WEB_SEARCH_PROVIDER.lower()
    log.info("web_search: tier=%s provider=%s running %d queries", tier_cfg.tier, provider, len(queries))

    all_results: list[SearchResult] = []
    seen_urls: set[str] = set()
    total_cost = 0.0
    for q in queries:
        results, cost = _dispatch(q, max_results=5)
        total_cost += cost
        # Record in the cost ledger so the daily cap query catches search spend.
        try:
            db.record_llm_call(
                LlmCall(
                    model=f"{provider}/search",
                    purpose="search",
                    tokens_in=0,
                    tokens_out=0,
                    cost_usd=cost,
                    latency_ms=None,
                    app_id=app_id,
                    ok=bool(results),
                )
            )
        except Exception as exc:
            log.warning("web_search: ledger write failed: %s", exc)
        for r in results:
            if r.url in seen_urls:
                continue
            seen_urls.add(r.url)
            all_results.append(r)
    log.info(
        "web_search: tier=%s queries=%d results=%d cost=$%.4f",
        tier_cfg.tier, len(queries), len(all_results), total_cost,
    )
    return SearchOutcome(
        results=all_results, queries_count=len(queries), cost_usd=total_cost
    )


def format_for_prompt(outcome: SearchOutcome) -> str:
    """Render search results as a context block for the generator prompt.
    Empty string when no results (caller should skip the section)."""
    if not outcome.results:
        return ""
    lines = [
        "Source material from web search (use as factual foundation; "
        "fabricated metrics, statuses, and visual decoration are still "
        "fine; named-attribution constraint applies):",
        "",
    ]
    for i, r in enumerate(outcome.results, 1):
        snippet = r.snippet[:600].strip()
        lines.append(f"[{i}] {r.title}")
        lines.append(f"    {r.url}")
        if snippet:
            lines.append(f"    {snippet}")
        lines.append("")
    return "\n".join(lines)
