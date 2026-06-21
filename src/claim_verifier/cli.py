from __future__ import annotations

import sys
from pathlib import Path

import typer
from dotenv import load_dotenv

app = typer.Typer(add_completion=False)

_VERDICT_LABELS = {
    "supported": "SUPPORTED",
    "contradicted": "CONTRADICTED",
    "insufficient_evidence": "INSUFFICIENT",
}

_VERDICT_COLORS = {
    "supported": typer.colors.GREEN,
    "contradicted": typer.colors.RED,
    "insufficient_evidence": typer.colors.YELLOW,
}


@app.command()
def verify(
    file: Path = typer.Argument(..., help="Text file to verify"),
    provider: str = typer.Option("parallel", "--provider", "-p", help="parallel or exa"),
) -> None:
    """Verify factual claims in a text file."""
    load_dotenv()

    if not file.exists():
        typer.echo(f"Error: file not found: {file}", err=True)
        raise typer.Exit(1)

    prose = file.read_text(encoding="utf-8")

    if provider == "parallel":
        from claim_verifier.retrieval.parallel import ParallelProvider
        p: object = ParallelProvider()
    elif provider == "exa":
        from claim_verifier.retrieval.exa import ExaProvider
        p = ExaProvider()
    else:
        typer.echo(f"Error: unknown provider '{provider}'. Choose parallel or exa.", err=True)
        raise typer.Exit(1)

    typer.echo(f"Verifying {file} with provider={provider} ...\n")

    from claim_verifier.orchestrator import verify as run_verify
    from claim_verifier.retrieval.base import RetrievalProvider
    report = run_verify(prose, p)  # type: ignore[arg-type]

    claim_count = sum(1 for s in report.sentences if s.is_claim)
    skip_count = len(report.sentences) - claim_count

    for result in report.sentences:
        if not result.is_claim:
            typer.echo(f"  [skip] {result.sentence}")
            continue

        label = _VERDICT_LABELS.get(result.verdict or "", result.verdict or "")
        color = _VERDICT_COLORS.get(result.verdict or "", typer.colors.WHITE)
        typer.secho(f"  [{label}] {result.sentence}", fg=color)

        if result.corrected_claim:
            typer.echo(f"           Correction: {result.corrected_claim}")

        if result.citation:
            date_str = f" ({result.citation.date})" if result.citation.date else ""
            typer.echo(f"           Source: {result.citation.title}{date_str}")
            typer.echo(f"           URL: {result.citation.url}")

        if result.confidence is not None:
            typer.echo(f"           Confidence: {result.confidence:.2f}")

        typer.echo()

    t = report.telemetry
    typer.echo("---")
    typer.echo(f"Sentences: {len(report.sentences)} total, {claim_count} claims, {skip_count} skipped")
    typer.echo(f"LLM calls: {t.llm_calls}  |  Retrieval calls: {t.retrieval_calls}  |  Estimated cost: ${t.estimated_cost_usd:.4f}")


@app.command()
def eval_run(
    provider: str = typer.Option("parallel", "--provider", "-p", help="parallel or exa or all"),
) -> None:
    """Run the evaluation harness against eval/gold_set.jsonl."""
    import subprocess

    load_dotenv()
    eval_script = Path(__file__).parent.parent.parent / "eval" / "run_eval.py"
    result = subprocess.run(
        [sys.executable, str(eval_script), "--provider", provider],
        check=False,
    )
    raise typer.Exit(result.returncode)


if __name__ == "__main__":
    app()
