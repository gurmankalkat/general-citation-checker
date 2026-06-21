from __future__ import annotations

import os
import parallel
from .base import RetrievalProvider
from ..schemas import EvidenceItem


class ParallelProvider(RetrievalProvider):
    cost_per_call: float = 0.01  # placeholder; update to published per-request pricing

    def __init__(self) -> None:
        api_key = os.environ.get("PARALLEL_API_KEY")
        if not api_key:
            raise EnvironmentError("PARALLEL_API_KEY is not set")
        self._client = parallel.Parallel(api_key=api_key)

    def search(self, query: str) -> list[EvidenceItem]:
        result = self._client.search(
            search_queries=[query],
            objective=query,
            mode="advanced",
        )
        items: list[EvidenceItem] = []
        for r in result.results:
            snippet = " ".join(r.excerpts) if r.excerpts else ""
            items.append(
                EvidenceItem(
                    title=r.title or "",
                    url=r.url,
                    snippet=snippet,
                    published_date=r.publish_date,
                )
            )
        return items
