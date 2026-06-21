from __future__ import annotations

import os
import anthropic
from .schemas import EvidenceItem, GradingResult, Citation

_MODEL = "claude-sonnet-4-6"

_SYSTEM = """You are a fact-checking engine. You will be given a single factual claim and a set of evidence snippets retrieved from the web.

Your job is to decide whether the evidence supports or contradicts the claim, or whether the evidence is insufficient to make a determination.

Rules:
- Choose "supported" only when at least one evidence snippet directly and specifically confirms the claim's key assertion.
- Choose "contradicted" when at least one evidence snippet directly conflicts with a specific detail in the claim (a wrong number, wrong year, wrong entity, etc.).
- Choose "insufficient_evidence" in all other cases: when the evidence is tangentially related, too vague, or simply does not address the specific assertion. Prefer this over guessing.
- When you choose "contradicted", populate corrected_claim with a rewritten version of the sentence using the correct fact from the evidence. Keep the rewrite minimal — change only what is wrong.
- When you choose "supported" or "contradicted", populate citation with the single best supporting source.
- Set confidence between 0.0 and 1.0. Be conservative. A high confidence requires a source that directly states the fact, not one that implies it."""

_TOOL_SCHEMA = {
    "name": "record_grading_result",
    "description": "Record the grading verdict for the claim.",
    "input_schema": {
        "type": "object",
        "properties": {
            "verdict": {
                "type": "string",
                "enum": ["supported", "contradicted", "insufficient_evidence"],
                "description": "Whether the evidence supports or contradicts the claim, or is insufficient.",
            },
            "corrected_claim": {
                "type": ["string", "null"],
                "description": "Rewritten sentence with the correct fact if verdict is contradicted, otherwise null.",
            },
            "citation_title": {
                "type": ["string", "null"],
                "description": "Title of the best supporting source, or null if verdict is insufficient_evidence.",
            },
            "citation_url": {
                "type": ["string", "null"],
                "description": "URL of the best supporting source, or null if verdict is insufficient_evidence.",
            },
            "citation_date": {
                "type": ["string", "null"],
                "description": "Publication date of the best supporting source if known, otherwise null.",
            },
            "confidence": {
                "type": "number",
                "description": "Confidence in the verdict, between 0.0 and 1.0.",
            },
        },
        "required": ["verdict", "corrected_claim", "citation_title", "citation_url", "citation_date", "confidence"],
    },
}


def _format_evidence(items: list[EvidenceItem]) -> str:
    parts = []
    for i, item in enumerate(items, 1):
        date_str = f" ({item.published_date})" if item.published_date else ""
        parts.append(f"[{i}] {item.title}{date_str}\n{item.url}\n{item.snippet[:800]}")
    return "\n\n".join(parts)


class GradingOutput:
    def __init__(self, result: GradingResult, input_tokens: int, output_tokens: int) -> None:
        self.result = result
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


def grade_claim(claim: str, evidence: list[EvidenceItem]) -> GradingOutput:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)

    user_message = (
        f"Claim to check:\n{claim}\n\n"
        f"Evidence:\n{_format_evidence(evidence)}"
    )

    response = client.messages.create(
        model=_MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        tools=[_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "record_grading_result"},
        messages=[{"role": "user", "content": user_message}],
    )

    tool_block = next(b for b in response.content if b.type == "tool_use")
    raw = tool_block.input

    citation = None
    if raw["citation_url"]:
        citation = Citation(
            title=raw["citation_title"] or "",
            url=raw["citation_url"],
            date=raw["citation_date"],
        )

    result = GradingResult(
        verdict=raw["verdict"],
        corrected_claim=raw["corrected_claim"],
        citation=citation,
        confidence=raw["confidence"],
    )

    return GradingOutput(
        result=result,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
