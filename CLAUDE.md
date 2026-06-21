# Claim Verifier

A standalone tool that takes prose, finds the sentences that make verifiable factual claims, retrieves evidence from the web, and grades whether the evidence supports each claim. Built on the Parallel API. Includes an evaluation harness and a side by side comparison against an Exa implementation of the same pipeline.

This is a portfolio artifact for a Deployed Engineer application at Parallel. It exists to demonstrate one thing. The ability to take a messy real world research process, decompose it into a selective agentic retrieval workflow, return structured verifiable output, and reason rigorously about accuracy and cost.

## What this is NOT

Do not build a Grammarly integration, a Grammarly UI clone, or any branded editor skin. The deliverable is a generic claim verification library plus a thin CLI and a minimal web demo. The point is infrastructure, not a consumer app wrapper.

Do not hardcode a single example or a single expected answer anywhere in the core logic. Every result must come from a live call. The only hardcoded data lives in the eval gold set described below.

## Writing rules for all docs, comments, and READMEs

- No em dashes.
- No semicolons.
- No colons inside prose sentences. Colons are allowed only to introduce code blocks or lists.
- Plain, human sounding prose. No marketing voice. No "leverage," "seamless," "robust," "powerful."
- When describing results, report numbers. Do not describe performance qualitatively where a measurement exists.

## Core thesis

Naive retrieval fires a search on every sentence. That is wasteful and noisy. The correct design retrieves only when a sentence asserts something checkable, then sends a structured query rather than the raw sentence, then grades the returned evidence against the specific claim. Cost per document and false positive rate are first class metrics, not afterthoughts.

## Architecture

Build four layers, each independently testable.

### 1. Claim detection
Input is a block of prose. Output is a list of sentences, each tagged with:
- `is_claim` boolean
- `claim_type` one of `quantitative`, `factual_assertion`, `attribution`, `none`
- `extracted_query` a structured search query if `is_claim` is true, otherwise null

Implement detection with an LLM call (Claude via the Anthropic API) using a strict JSON output schema. Prompt it to skip narrative, opinion, hedged statements, and first person. The query rewrite step is part of detection. The raw sentence "There are 50 new health tech startups in SF" becomes a query like "number of newly funded health tech startups San Francisco 2025 2026" with the entities and the time window pulled out.

### 2. Retrieval (pluggable provider interface)
Define an abstract `RetrievalProvider` interface with a single method that takes a query string and returns a normalized list of `{title, url, snippet, published_date}`.

Implement two concrete providers:
- `ParallelProvider` using the Parallel Search API via the `parallel-web` package. This is the primary provider.
- `ExaProvider` using the Exa API. This exists for the comparison only.

The rest of the pipeline must not know or care which provider is active. The provider is selected by a config flag or CLI argument.

### 3. Evidence grading
Input is one claim plus the retrieved evidence for it. Output is structured:
- `verdict` one of `supported`, `contradicted`, `insufficient_evidence`
- `corrected_claim` a rewritten sentence with the right number or fact if contradicted, otherwise null
- `citation` the supporting source title, url, and date
- `confidence` a float

Use an LLM call with a narrow prompt. The grader sees only the one claim and its evidence, never the whole document. Force it to choose `insufficient_evidence` rather than guessing when the evidence does not directly address the claim. This is the most important failure mode to get right and the eval must measure it.

### 4. Orchestrator
Ties the three together. Takes a document, runs detection once, fires retrieval only on detected claims, grades each, and returns a structured report listing every sentence with its verdict and citation. Track and return cost telemetry per run. Number of LLM calls, number of retrieval calls, and estimated dollar cost using current published per request pricing for each provider.

## Evaluation harness

This is not optional and it is the part that matters most. Build `eval/run_eval.py`.

Create a gold set of at least 40 sentences in `eval/gold_set.jsonl`. Mix:
- Sentences with no claim (narrative, opinion, transitions). Roughly one third.
- True quantitative and factual claims that are correct.
- Claims that are subtly wrong (right entity, wrong number or wrong year). These are the hard cases.

Each gold row has the sentence, the correct `is_claim` label, and for real claims the correct verdict and the true fact.

The eval must report, for each retrieval provider:
- Claim detection precision and recall.
- Verdict accuracy on the claims that should have been retrieved.
- False positive rate on `supported` verdicts. That is, how often it says supported when the claim is actually wrong. Weight this heavily in the writeup. A citation tool that confidently validates wrong claims is worse than useless.
- Average retrieval calls per document and estimated cost per document.

Output a single markdown table comparing Parallel and Exa across all of these metrics.

## Failure analysis

Write `FINDINGS.md` by hand after running the eval. It must include:
- The comparison table.
- A short section naming the specific gold set items where each provider failed, with the actual wrong output quoted.
- An honest account of where Parallel surprised you, including cases where it lost to Exa or where the grader was fooled. Do not sand this down. The willingness to publish where it broke is the entire signal.

## Tech stack

- Python 3.11.
- `parallel-web` for Parallel, official Exa SDK for Exa, `anthropic` for the LLM layer.
- Pydantic for all structured schemas so detection and grading outputs are validated, not parsed by hand.
- A thin CLI with `argparse` or `typer`. One command verifies a text file, one command runs the eval.
- Optional minimal web demo using FastAPI plus a single static HTML page with a textarea and a "verify" button that calls the backend. Keep it ugly and functional. No framework, no Grammarly styling.
- Keys via environment variables. Never commit keys. Provide a `.env.example`.

## Repo layout

```
claim-verifier/
  README.md
  FINDINGS.md
  CLAUDE.md
  .env.example
  pyproject.toml
  src/claim_verifier/
    schemas.py          # Pydantic models
    detection.py        # layer 1
    retrieval/
      base.py           # RetrievalProvider interface
      parallel.py       # layer 2 Parallel
      exa.py            # layer 2 Exa
    grading.py          # layer 3
    orchestrator.py     # layer 4
    cli.py
  web/
    app.py              # FastAPI
    index.html
  eval/
    gold_set.jsonl
    run_eval.py
```

## README requirements

The README must lead with the problem and the design decision, not with setup steps. Open by explaining why selective retrieval beats per sentence retrieval and why structured query rewriting matters. Then the architecture. Then the eval results table copied from FINDINGS. Then setup. A reviewer should understand the thinking in the first thirty seconds.

## Build order

1. Schemas first.
2. Detection layer with a few quick manual tests.
3. The provider interface and the Parallel provider. Verify a live call returns normalized results.
4. Grading layer.
5. Orchestrator with cost telemetry.
6. The Exa provider.
7. The eval harness and gold set.
8. Run the eval, write FINDINGS by hand.
9. README last, once you know the real numbers.
10. Web demo only if everything above is done.

Do not skip the eval to get to the demo faster. A demo with no eval is the weak version of this project and defeats its purpose.
