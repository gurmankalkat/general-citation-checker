# Claim Verifier

Most fact-checking tools fire a search query for every sentence in a document. That is the wrong default. The majority of sentences in any real piece of writing are not checkable claims. They are transitions, opinions, narrative, hedges. Running retrieval on all of them wastes money, adds noise to the results, and slows everything down.

This tool does it differently. It reads the full document once with a language model to identify which sentences assert something verifiable, rewrites each one into a structured search query with entities and time windows extracted, retrieves evidence only for those sentences, and grades each claim against its evidence. A document with 60 sentences might contain 47 verifiable claims. The other 13 never touch the retrieval layer.

Query rewriting is the second design decision that matters. The raw sentence "Alphabet reported annual revenue of $250 billion in 2023" is a bad search query. The rewritten version, something like "Alphabet Google annual revenue 2023 fiscal year," is not. The rewrite step pulls out the entities, strips the framing, and adds relevant date context so the retrieval provider returns documents that actually address the specific claim rather than the topic area around it.

The third decision is about grading. The grader sees only one claim and its evidence at a time, never the whole document. It is forced to choose `insufficient_evidence` rather than guess when the evidence does not directly address the claim. A citation tool that confidently validates wrong claims is worse than useless. The false positive rate on `supported` verdicts for actually-wrong claims is the metric this project treats as most important.

## Architecture

Four layers, each independently testable.

**Detection** takes a block of prose and calls Claude via the Anthropic API with a forced tool-use schema. The output is a list of sentences, each tagged with `is_claim`, `claim_type` (quantitative, factual assertion, attribution, or none), and an `extracted_query` if it is a claim. Narrative, opinion, hedged statements, and first-person sentences are skipped. This is one LLM call per document regardless of length.

**Retrieval** is a pluggable interface. Two providers are implemented: Parallel (via `parallel-web`) and Exa (via `exa-py`). Both return the same normalized structure of title, URL, snippet, and date. The rest of the pipeline does not know which provider is active.

**Grading** takes one claim and its retrieved evidence. It calls Claude again with a narrow prompt and a forced tool-use schema that returns a verdict, an optional corrected claim, a citation, and a confidence score. The grader is instructed to prefer `insufficient_evidence` over guessing, and to produce a corrected rewrite only when the verdict is `contradicted`.

**Orchestrator** ties the three layers together. It runs detection once, fires retrieval only for detected claims, grades each, and returns a structured report with every sentence's verdict and citation. It tracks and returns cost telemetry: number of LLM calls, number of retrieval calls, and estimated dollar cost using published per-request pricing.

All schemas are Pydantic models. Detection and grading outputs are validated, not parsed by hand.

## Eval results

The eval harness runs both providers against a 60-sentence gold set. The set mixes non-claims (narrative, opinion, transitions), correct factual claims, and subtly wrong claims where the entity is right but the year or number is off. The most important metric is the false positive rate on `supported` verdicts, which measures how often the pipeline confidently validates a wrong claim.

| Metric | Parallel | Exa |
|---|---|---|
| Detection precision | 1.00 | 1.00 |
| Detection recall | 1.00 | 1.00 |
| Detection F1 | 1.00 | 1.00 |
| Verdict accuracy | 0.94 | 0.91 |
| FP rate (supported / wrong) | 0.07 | 0.11 |
| Retrieval calls | 47 | 47 |
| Estimated cost (USD) | $1.18 | $0.99 |

Detection was perfect for both providers on this gold set. The difference shows up in grading. Parallel produced 44 of 47 correct verdicts and incorrectly validated 2 of 27 wrong claims as supported. Exa produced 43 of 47 correct verdicts and incorrectly validated 3 of 27 wrong claims as supported. Exa is 16% cheaper per run. Parallel makes fewer false confidence mistakes.

Both providers got the same three verdicts wrong. "Bitcoin was created by a person named Satoshi Nakamoto" was labeled supported by both, because most web sources treat Satoshi as a person without qualification. "Google holds more than 90% of the global search market" was labeled supported by both, because the claim sits close enough to the actual figure that sources exist on both sides. "There are 8 billion people on Earth" was labeled contradicted by both, because current estimates land at 8.3 billion and both graders treated the round number as wrong rather than approximate. Full failure analysis is in `FINDINGS.md`.

## Setup

**Requirements:** Python 3.11, API keys for Anthropic, Parallel, and Exa.

```
git clone https://github.com/gurmankalkat/general-citation-checker
cd general-citation-checker
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env
# fill in your API keys in .env
```

**Verify a document:**

```
claim-verifier verify sample.txt --provider parallel
claim-verifier verify sample.txt --provider exa
```

**Run the eval:**

```
python eval/run_eval.py --provider all
```

Or via the CLI:

```
claim-verifier eval-run --provider all
```

**Environment variables:**

```
ANTHROPIC_API_KEY=...
PARALLEL_API_KEY=...
EXA_API_KEY=...
```

## Repo layout

```
src/claim_verifier/
  schemas.py        Pydantic models
  detection.py      layer 1: claim detection and query rewriting
  retrieval/
    base.py         RetrievalProvider interface
    parallel.py     Parallel Search API provider
    exa.py          Exa provider
  grading.py        layer 3: evidence grading
  orchestrator.py   layer 4: ties the pipeline together with cost telemetry
  cli.py            CLI entry point
eval/
  gold_set.jsonl    60-sentence gold set with verified labels
  run_eval.py       evaluation harness
FINDINGS.md         failure analysis written after running the eval
```
