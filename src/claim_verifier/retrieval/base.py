from __future__ import annotations

from abc import ABC, abstractmethod
from ..schemas import EvidenceItem


class RetrievalProvider(ABC):
    cost_per_call: float = 0.0

    @abstractmethod
    def search(self, query: str) -> list[EvidenceItem]:
        ...
