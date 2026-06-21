from __future__ import annotations

import os

import exa_py

from .base import RetrievalProvider
from ..schemas import EvidenceItem


class ExaProvider(RetrievalProvider):
    cost_per_call: float = 0.01  # placeholder; update to published per-request pricing

    def __init__(self) -> None:
        api_key = os.environ.get("EXA_API_KEY")
        if not api_key:
            raise EnvironmentError("EXA_API_KEY is not set")
        self._client = exa_py.Exa(api_key=api_key)

    def search(self, query: str) -> list[EvidenceItem]:
        response = self._client.search(
            query,
            num_results=5,
            contents={"text": {"max_characters": 1000}, "highlights": {"num_sentences": 3}},
        )
        items: list[EvidenceItem] = []
        for r in response.results:
            if r.highlights:
                snippet = " ".join(r.highlights)
            elif r.text:
                snippet = r.text[:800]
            else:
                snippet = ""
            items.append(
                EvidenceItem(
                    title=r.title or "",
                    url=r.url,
                    snippet=snippet,
                    published_date=r.published_date,
                )
            )
        return items
