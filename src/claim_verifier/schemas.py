from __future__ import annotations

from typing import Optional, Literal
from pydantic import BaseModel, Field


ClaimType = Literal["quantitative", "factual_assertion", "attribution", "none"]
Verdict = Literal["supported", "contradicted", "insufficient_evidence"]


class DetectedClaim(BaseModel):
    sentence: str
    is_claim: bool
    claim_type: ClaimType
    extracted_query: Optional[str] = None


class DetectionResult(BaseModel):
    claims: list[DetectedClaim]
    input_tokens: int
    output_tokens: int


class EvidenceItem(BaseModel):
    title: str
    url: str
    snippet: str
    published_date: Optional[str] = None


class Citation(BaseModel):
    title: str
    url: str
    date: Optional[str] = None


class GradingResult(BaseModel):
    verdict: Verdict
    corrected_claim: Optional[str] = None
    citation: Optional[Citation] = None
    confidence: float = Field(ge=0.0, le=1.0)


class SentenceResult(BaseModel):
    sentence: str
    is_claim: bool
    claim_type: ClaimType
    extracted_query: Optional[str] = None
    verdict: Optional[Verdict] = None
    corrected_claim: Optional[str] = None
    citation: Optional[Citation] = None
    confidence: Optional[float] = None


class CostTelemetry(BaseModel):
    llm_calls: int
    retrieval_calls: int
    estimated_cost_usd: float


class VerificationReport(BaseModel):
    sentences: list[SentenceResult]
    telemetry: CostTelemetry
