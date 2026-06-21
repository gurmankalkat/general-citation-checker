from __future__ import annotations

import os
import anthropic
from .schemas import DetectedClaim, DetectionResult

_MODEL = "claude-sonnet-4-6"

_SYSTEM = """You are a claim detection engine. Your job is to read a block of prose and identify every sentence that makes a verifiable factual claim.

A sentence IS a claim if it asserts something that could be checked against real world sources:
- A specific number, statistic, or measurement (quantitative)
- A stated fact about an entity, event, place, or thing (factual_assertion)
- A statement attributed to a named person or organization (attribution)

A sentence is NOT a claim if it is:
- Narrative or scene-setting ("The conference was held downtown")
- Opinion or subjective judgment ("The policy seems misguided")
- Hedged or uncertain ("It might be that rates will rise")
- First-person ("I think the data shows a trend")
- A transition or rhetorical framing ("This raises an important question")

For every sentence that IS a claim, rewrite it as a concise structured search query. Pull out the specific entities, numbers, and time window. Do not repeat the raw sentence as the query. For example:
- Raw: "There are 50 new health tech startups in SF this year"
- Query: "number newly funded health tech startups San Francisco 2025 2026"

Set extracted_query to null for non-claims."""

_TOOL_SCHEMA = {
    "name": "record_claim_analysis",
    "description": "Record the claim analysis for each sentence in the document.",
    "input_schema": {
        "type": "object",
        "properties": {
            "sentences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "sentence": {
                            "type": "string",
                            "description": "The original sentence text.",
                        },
                        "is_claim": {
                            "type": "boolean",
                            "description": "True if the sentence makes a verifiable factual claim.",
                        },
                        "claim_type": {
                            "type": "string",
                            "enum": ["quantitative", "factual_assertion", "attribution", "none"],
                            "description": "Category of claim. Use 'none' when is_claim is false.",
                        },
                        "extracted_query": {
                            "type": ["string", "null"],
                            "description": "Structured search query if is_claim is true, otherwise null.",
                        },
                    },
                    "required": ["sentence", "is_claim", "claim_type", "extracted_query"],
                },
            }
        },
        "required": ["sentences"],
    },
}


def detect_claims(prose: str) -> DetectionResult:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set")

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=_SYSTEM,
        tools=[_TOOL_SCHEMA],
        tool_choice={"type": "tool", "name": "record_claim_analysis"},
        messages=[
            {
                "role": "user",
                "content": f"Analyze every sentence in the following text:\n\n{prose}",
            }
        ],
    )

    tool_block = next(b for b in response.content if b.type == "tool_use")
    raw_sentences = tool_block.input["sentences"]

    claims = [DetectedClaim(**s) for s in raw_sentences]

    return DetectionResult(
        claims=claims,
        input_tokens=response.usage.input_tokens,
        output_tokens=response.usage.output_tokens,
    )
