from __future__ import annotations

from .detection import detect_claims
from .grading import grade_claim
from .retrieval.base import RetrievalProvider
from .schemas import CostTelemetry, SentenceResult, VerificationReport

# Claude Sonnet 4.6 published pricing
_INPUT_COST_PER_TOKEN = 3.00 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 15.00 / 1_000_000


def verify(prose: str, provider: RetrievalProvider) -> VerificationReport:
    detection = detect_claims(prose)

    total_input_tokens = detection.input_tokens
    total_output_tokens = detection.output_tokens
    llm_calls = 1
    retrieval_calls = 0

    sentence_results: list[SentenceResult] = []

    for claim in detection.claims:
        if not claim.is_claim or claim.extracted_query is None:
            sentence_results.append(
                SentenceResult(
                    sentence=claim.sentence,
                    is_claim=False,
                    claim_type=claim.claim_type,
                )
            )
            continue

        evidence = provider.search(claim.extracted_query)
        retrieval_calls += 1

        grading = grade_claim(claim.sentence, evidence)
        llm_calls += 1
        total_input_tokens += grading.input_tokens
        total_output_tokens += grading.output_tokens

        sentence_results.append(
            SentenceResult(
                sentence=claim.sentence,
                is_claim=True,
                claim_type=claim.claim_type,
                extracted_query=claim.extracted_query,
                verdict=grading.result.verdict,
                corrected_claim=grading.result.corrected_claim,
                citation=grading.result.citation,
                confidence=grading.result.confidence,
            )
        )

    llm_cost = (
        total_input_tokens * _INPUT_COST_PER_TOKEN
        + total_output_tokens * _OUTPUT_COST_PER_TOKEN
    )
    retrieval_cost = retrieval_calls * provider.cost_per_call
    estimated_cost = llm_cost + retrieval_cost

    telemetry = CostTelemetry(
        llm_calls=llm_calls,
        retrieval_calls=retrieval_calls,
        estimated_cost_usd=round(estimated_cost, 6),
    )

    return VerificationReport(sentences=sentence_results, telemetry=telemetry)
