"""
IntelliCredit — Web Searcher
DuckDuckGo search wrapper with retry and batch support.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List

from ddgs import DDGS


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    query: str


def search(query: str, max_results: int = 5, retries: int = 3) -> List[SearchResult]:
    """
    Search DuckDuckGo with exponential-backoff retry.
    Returns a list of SearchResult.
    """
    for attempt in range(retries):
        try:
            with DDGS() as ddgs:
                raw = list(ddgs.text(query, max_results=max_results))

            results: list[SearchResult] = []
            for item in raw:
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("href", item.get("link", "")),
                        snippet=item.get("body", item.get("snippet", "")),
                        query=query,
                    )
                )
            return results

        except Exception as exc:  # noqa: BLE001
            wait = 2 ** attempt
            print(f"  ⚠ Search failed (attempt {attempt + 1}/{retries}): {exc}")
            if attempt < retries - 1:
                print(f"    Retrying in {wait}s …")
                time.sleep(wait)

    return []


def batch_search(
    queries: List[str],
    max_results_per_query: int = 5,
    delay_between_queries: float = 1.5,
) -> Dict[str, List[SearchResult]]:
    """
    Run multiple queries sequentially with a delay between each.
    Returns a dict mapping query string → list[SearchResult].
    """
    results: dict[str, list[SearchResult]] = {}
    for idx, query in enumerate(queries):
        print(f"  🔍 [{idx + 1}/{len(queries)}] {query}")
        results[query] = search(query, max_results=max_results_per_query)
        if idx < len(queries) - 1:
            time.sleep(delay_between_queries)
    return results
