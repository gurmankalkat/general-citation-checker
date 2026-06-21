#!/usr/bin/env python3
"""
Evaluation harness for the claim verifier pipeline.

Usage:
    python eval/run_eval.py --provider parallel
    python eval/run_eval.py --provider exa
    python eval/run_eval.py --provider all
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from claim_verifier.orchestrator import verify
from claim_verifier.retrieval.base import RetrievalProvider
from claim_verifier.schemas import SentenceResult, VerificationReport

GOLD_PATH = Path(__file__).parent / "gold_set.jsonl"


def load_gold(path: Path) -> list[dict]:
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                rows.append(json.loads(line))
    return rows


def build_provider(name: str) -> RetrievalProvider:
    if name == "parallel":
        from claim_verifier.retrieval.parallel import ParallelProvider
        return ParallelProvider()
    if name == "exa":
        from claim_verifier.retrieval.exa import ExaProvider
        return ExaProvider()
    raise ValueError(f"Unknown provider: {name!r}")


def find_result(
    sentence: str,
    result_map: dict[str, SentenceResult],
) -> Optional[SentenceResult]:
    key = sentence.strip()
    if key in result_map:
        return result_map[key]
    best: Optional[SentenceResult] = None
    best_score = 0.0
    for k, r in result_map.items():
        score = difflib.SequenceMatcher(None, key.lower(), k.lower()).ratio()
        if score > best_score:
            best_score = score
            best = r
    if best_score >= 0.85:
        return best
    return None


def eval_provider(gold: list[dict], provider: RetrievalProvider) -> dict:
    prose = "\n".join(row["sentence"] for row in gold)
    report: VerificationReport = verify(prose, provider)
    result_map = {r.sentence.strip(): r for r in report.sentences}

    tp = fp = fn = tn = 0
    verdict_correct = verdict_total = 0
    supported_when_wrong = 0
    total_contradicted = 0
    unmatched: list[str] = []
    failure_log: list[dict] = []

    for row in gold:
        sentence: str = row["sentence"]
        gold_is_claim: bool = row["is_claim"]
        gold_verdict: Optional[str] = row.get("verdict")
        result = find_result(sentence, result_map)

        if result is None:
            unmatched.append(sentence[:70])
            continue

        pred_is_claim = result.is_claim

        if gold_is_claim and pred_is_claim:
            tp += 1
        elif gold_is_claim and not pred_is_claim:
            fn += 1
            failure_log.append({
                "type": "missed_claim",
                "id": row.get("id"),
                "sentence": sentence[:80],
            })
        elif not gold_is_claim and pred_is_claim:
            fp += 1
            failure_log.append({
                "type": "false_detection",
                "id": row.get("id"),
                "sentence": sentence[:80],
                "predicted_verdict": result.verdict,
            })
        else:
            tn += 1

        if (
            gold_is_claim
            and gold_verdict is not None
            and pred_is_claim
            and result.verdict is not None
        ):
            verdict_total += 1
            if result.verdict == gold_verdict:
                verdict_correct += 1
            else:
                failure_log.append({
                    "type": "wrong_verdict",
                    "id": row.get("id"),
                    "sentence": sentence[:80],
                    "gold": gold_verdict,
                    "predicted": result.verdict,
                    "corrected_claim": result.corrected_claim,
                })

        if gold_is_claim and gold_verdict == "contradicted":
            total_contradicted += 1
            if pred_is_claim and result.verdict == "supported":
                supported_when_wrong += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    verdict_acc = verdict_correct / verdict_total if verdict_total > 0 else 0.0
    fp_rate = (
        supported_when_wrong / total_contradicted if total_contradicted > 0 else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "verdict_accuracy": verdict_acc,
        "fp_supported_rate": fp_rate,
        "retrieval_calls": report.telemetry.retrieval_calls,
        "estimated_cost_usd": report.telemetry.estimated_cost_usd,
        "llm_calls": report.telemetry.llm_calls,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "verdict_correct": verdict_correct,
        "verdict_total": verdict_total,
        "supported_when_wrong": supported_when_wrong,
        "total_contradicted": total_contradicted,
        "unmatched": unmatched,
        "failure_log": failure_log,
    }


def print_table(provider_names: list[str], results: list[dict]) -> None:
    rows = [
        ("Detection precision", [f"{r['precision']:.2f}" for r in results]),
        ("Detection recall", [f"{r['recall']:.2f}" for r in results]),
        ("Detection F1", [f"{r['f1']:.2f}" for r in results]),
        ("Verdict accuracy", [f"{r['verdict_accuracy']:.2f}" for r in results]),
        ("FP rate (supported / wrong)", [f"{r['fp_supported_rate']:.2f}" for r in results]),
        ("Retrieval calls", [str(r["retrieval_calls"]) for r in results]),
        ("Estimated cost (USD)", [f"${r['estimated_cost_usd']:.4f}" for r in results]),
    ]

    headers = ["Metric"] + [n.capitalize() for n in provider_names]

    col_widths: list[int] = []
    col_widths.append(max(len(headers[0]), max(len(label) for label, _ in rows)))
    for i, name in enumerate(provider_names):
        col_widths.append(
            max(len(headers[i + 1]), max(len(vals[i]) for _, vals in rows))
        )

    def fmt(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(col_widths[i]) for i, c in enumerate(cells)) + " |"

    def sep() -> str:
        return "|" + "|".join("-" * (w + 2) for w in col_widths) + "|"

    print(fmt(headers))
    print(sep())
    for label, vals in rows:
        print(fmt([label] + vals))


def print_failures(provider_name: str, metrics: dict) -> None:
    print(f"\n=== {provider_name.upper()} FAILURES ===")
    print(
        f"Detection: TP={metrics['tp']} FP={metrics['fp']} "
        f"FN={metrics['fn']} TN={metrics['tn']}"
    )
    print(
        f"Verdict: {metrics['verdict_correct']}/{metrics['verdict_total']} correct"
    )
    print(
        f"False supports on wrong claims: "
        f"{metrics['supported_when_wrong']}/{metrics['total_contradicted']}"
    )

    if metrics["unmatched"]:
        print(f"\nUnmatched ({len(metrics['unmatched'])}):")
        for s in metrics["unmatched"]:
            print(f"  - {s}")

    if metrics["failure_log"]:
        print(f"\nFailure log ({len(metrics['failure_log'])}):")
        for f in metrics["failure_log"]:
            ftype = f["type"]
            fid = f.get("id", "?")
            sentence = f["sentence"]
            if ftype == "missed_claim":
                print(f"  [id={fid}] MISSED CLAIM: {sentence}")
            elif ftype == "false_detection":
                print(f"  [id={fid}] FALSE DETECTION: {sentence}")
            elif ftype == "wrong_verdict":
                print(
                    f"  [id={fid}] WRONG VERDICT: {sentence}"
                    f"\n             gold={f['gold']} predicted={f['predicted']}"
                )
                if f.get("corrected_claim"):
                    print(f"             correction: {f['corrected_claim']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate claim verifier against the gold set."
    )
    parser.add_argument(
        "--provider",
        choices=["parallel", "exa", "all"],
        default="parallel",
        help="Retrieval provider to evaluate (default: parallel).",
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=GOLD_PATH,
        help="Path to the gold set JSONL file.",
    )
    args = parser.parse_args()

    gold = load_gold(args.gold)
    unverified = [r for r in gold if r.get("needs_verification", False)]
    verified = [r for r in gold if not r.get("needs_verification", False)]

    if unverified and not verified:
        print(
            f"WARNING: All {len(gold)} rows have needs_verification=true. "
            "Labels have not been confirmed by hand."
        )
        print(
            "Running anyway for pipeline validation. "
            "Metrics are not meaningful until labels are verified.\n"
        )
        to_eval = gold
    elif unverified:
        print(
            f"Note: {len(unverified)} of {len(gold)} rows still have "
            f"needs_verification=true and are excluded."
        )
        print(f"Running on {len(verified)} verified rows.\n")
        to_eval = verified
    else:
        to_eval = gold

    providers_to_run = (
        ["parallel", "exa"] if args.provider == "all" else [args.provider]
    )

    all_metrics: list[dict] = []
    for pname in providers_to_run:
        print(f"Running {pname} on {len(to_eval)} sentences...", flush=True)
        provider = build_provider(pname)
        metrics = eval_provider(to_eval, provider)
        all_metrics.append(metrics)
        print(
            f"  Done. LLM calls={metrics['llm_calls']} "
            f"retrieval calls={metrics['retrieval_calls']} "
            f"cost=${metrics['estimated_cost_usd']:.4f}"
        )

    print()
    print_table(providers_to_run, all_metrics)
    print()

    for pname, metrics in zip(providers_to_run, all_metrics):
        print_failures(pname, metrics)


if __name__ == "__main__":
    main()
