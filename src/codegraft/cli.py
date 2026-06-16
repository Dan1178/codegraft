"""codegraft command-line interface.

Phase 1 surface:
- ``init``    write a default codegraft.toml and report env-key requirements
- ``inspect`` placeholder; the real deterministic-analysis preview lands in Phase 3
- ``plan``    run the (stub) end-to-end path and write a Markdown plan to /plans
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from codegraft import __version__

# Rich + the legacy Windows console default to the active code page (often
# cp1252), which crashes on non-ASCII output — including arbitrary model-
# generated plan text printed via --stdout. Force UTF-8 with a replacement
# fallback so output never raises a UnicodeEncodeError.
for _stream in (sys.stdout, sys.stderr):
    reconfigure = getattr(_stream, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
from codegraft.branding import BANNER, TAGLINE
from codegraft.config import CONFIG_FILENAME, DEFAULT_CONFIG_TOML, Config
from codegraft.errors import CodegraftError
from codegraft.planning.filenames import plan_stem
from codegraft.planning.renderer import render_markdown
from codegraft.planning.service import build_stub_plan

app = typer.Typer(
    name="codegraft",
    help=f"{TAGLINE}",
    no_args_is_help=True,
    add_completion=True,
)
# legacy_windows=False keeps Rich on the standard write path (honouring the
# UTF-8 reconfigure above) instead of the win32 console API that encodes with
# the system code page.
console = Console(legacy_windows=False)
err_console = Console(stderr=True, legacy_windows=False)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"codegraft {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """codegraft — implementation plans for coding agents."""


@app.command()
def init(
    repo: Path = typer.Option(
        Path("."), "--repo", help="Repository root to initialize.",
        file_okay=False, dir_okay=True, resolve_path=True,
    ),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing config."),
) -> None:
    """Create a ``codegraft.toml`` and print required environment keys."""

    console.print(BANNER)
    config_path = repo / CONFIG_FILENAME
    if config_path.exists() and not force:
        err_console.print(
            f"[yellow]{CONFIG_FILENAME} already exists[/yellow] at {config_path}. "
            "Use --force to overwrite."
        )
        raise typer.Exit(code=1)

    config_path.write_text(DEFAULT_CONFIG_TOML, encoding="utf-8")
    console.print(f"[green]Wrote[/green] {config_path}")
    console.print(
        "\nSet provider keys in your environment or a [bold].env[/bold] file:\n"
        "  [dim]ANTHROPIC_API_KEY=...[/dim]\n"
        "  [dim]OPENAI_API_KEY=...[/dim]\n"
    )


@app.command()
def inspect(
    request: str = typer.Argument(
        None, help="Feature request to rank files for. Omit to show summary only."
    ),
    repo: Path = typer.Option(
        Path("."), "--repo", help="Repository root to analyze.",
        file_okay=False, dir_okay=True, resolve_path=True,
    ),
    request_file: Optional[Path] = typer.Option(
        None, "--request-file", help="Read the feature request from a file.",
        exists=True, dir_okay=False, resolve_path=True,
    ),
    subdir: Optional[str] = typer.Option(
        None, "--subdir", help="Scope analysis to a repo-relative subdirectory."
    ),
    snippets: bool = typer.Option(
        False, "--snippets", help="Also print the extracted context snippets."
    ),
) -> None:
    """Preview what codegraft sees and ranks for a request (no model call).

    With a request, this is the ranking/tuning surface: repo summary, the
    deterministically-ranked files with their score breakdown, and the bounded
    context snippets that would be sent to a provider. Pair with --request-file
    to preview ranking for a long-form request before spending an API call.
    """

    from rich.table import Table

    from codegraft.repo.analyze import analyze_repo

    try:
        request_text = _read_request(request, request_file, required=False)
        config = Config.load(repo)
        analysis = analyze_repo(request_text or "", repo, config, subdir=subdir)
    except CodegraftError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1)
    request = request_text  # may be None for summary-only mode

    scan, summary = analysis.scan, analysis.summary
    console.print(BANNER)

    source = "git ls-files" if scan.used_git else "filesystem walk (no git)"
    scope = f"  Subdir: [bold]{subdir}[/bold]" if subdir else ""
    console.print(
        f"\nRepo: {scan.root}{scope}\n"
        f"Discovery: [bold]{source}[/bold]  Kept: [green]{scan.file_count}[/green]  "
        f"Skipped: [yellow]{len(scan.skipped)}[/yellow]  "
        f"Mode: [bold]{summary.mode}[/bold]"
        + ("  [red](truncated)[/red]" if scan.truncated else "")
    )
    if summary.mode == "large":
        console.print(
            "[yellow]Large repo[/yellow] — ranking is conservative; "
            "consider scoping with [bold]--subdir[/bold]."
        )

    lang_mix = "  ".join(f"{lang}={n}" for lang, n in list(summary.languages.items())[:6])
    console.print(
        f"[dim]Primary:[/dim] {summary.primary_language or '—'}   "
        f"[dim]Frameworks:[/dim] {', '.join(summary.frameworks) or '—'}\n"
        f"[dim]Languages:[/dim] {lang_mix or '—'}\n"
        f"[dim]Manifests:[/dim] {', '.join(summary.manifests[:6]) or '—'}\n"
        f"[dim]Entry points:[/dim] {', '.join(summary.entry_points[:6]) or '—'}"
    )

    if not request:
        console.print(
            "\n[dim]Pass a feature request to see ranked files, e.g.:[/dim]\n"
            '  codegraft inspect "add role-based access control"'
        )
        return

    # A long request is ranked by a focused signal — show it so the user knows
    # what actually drove file selection.
    if analysis.ranking_signal.strip() != (request or "").strip():
        console.print(
            f"[dim]Ranking signal:[/dim] [italic]{analysis.ranking_signal}[/italic] "
            "[dim](full request still goes to the model)[/dim]"
        )

    if not analysis.ranked:
        console.print(
            f"\n[yellow]No files ranked[/yellow] for: [italic]{analysis.ranking_signal}[/italic]\n"
            "[dim]Try more specific keywords, or widen --subdir.[/dim]"
        )
        return

    flat_req = " ".join(request.split())
    title_req = flat_req if len(flat_req) <= 60 else flat_req[:57] + "..."
    table = Table(title=f"Ranked files for: {title_req}")
    table.add_column("#", justify="right")
    table.add_column("Score", justify="right")
    table.add_column("Path", overflow="fold")
    table.add_column("Signals", overflow="fold")
    for i, r in enumerate(analysis.ranked, 1):
        signals = "  ".join(
            f"{k}={v:+.1f}" for k, v in sorted(r.signals.items(), key=lambda kv: -abs(kv[1]))
        )
        table.add_row(str(i), f"{r.score:.1f}", r.path, signals)
    console.print(table)
    console.print(
        f"[dim]Context bundle:[/dim] {len(analysis.snippets)} snippets, "
        f"{analysis.context_chars} chars "
        f"(budget {config.analysis.context_char_budget})"
    )
    est = analysis.token_estimate()
    console.print(f"[dim]Est. tokens (rough):[/dim] {est.summary()}")

    if snippets:
        for s in analysis.snippets:
            console.print(f"\n[bold cyan]{s.path}[/bold cyan] "
                          f"[dim]({s.line_count} lines"
                          + (", truncated" if s.truncated else "") + ")[/dim]")
            console.print(s.content)


@app.command()
def plan(
    request: str = typer.Argument(
        None, help="Feature request. Omit when using --request-file."
    ),
    repo: Path = typer.Option(
        Path("."), "--repo", help="Repository root to plan against.",
        file_okay=False, dir_okay=True, resolve_path=True,
    ),
    request_file: Optional[Path] = typer.Option(
        None, "--request-file", help="Read the feature request from a file.",
        exists=True, dir_okay=False, resolve_path=True,
    ),
    subdir: Optional[str] = typer.Option(
        None, "--subdir", help="Scope analysis to a repo-relative subdirectory."
    ),
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Override provider (anthropic|openai)."
    ),
    model: Optional[str] = typer.Option(None, "--model", help="Override model id."),
    stub: bool = typer.Option(
        False, "--stub", help="Offline placeholder plan; no repo analysis, no API call."
    ),
    stdout: bool = typer.Option(
        False, "--stdout", help="Print the plan to stdout instead of a file."
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the plan as JSON to stdout (for scripting)."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Build the plan but do not write any file."
    ),
) -> None:
    """Generate an implementation plan and write it to the output directory.

    Calls the configured provider (default: anthropic) to produce a real,
    evidence-backed plan. Use --stub to produce an offline placeholder without an
    API key.
    """

    from codegraft.planning.service import generate_plan

    try:
        request_text = _read_request(request, request_file, required=True)
        config = Config.load(repo)
        if provider:
            config.provider.name = provider
        if model:
            config.provider.model = model

        if stub:
            plan_obj = build_stub_plan(request_text, repo, config)
        else:
            with console.status(
                f"Analyzing repo and planning with "
                f"{config.provider.name}/{config.provider.model}..."
            ):
                plan_obj = generate_plan(request_text, repo, config, subdir=subdir)

        if as_json:
            # Plain echo so Rich markup/reflow can't corrupt the JSON.
            typer.echo(plan_obj.model_dump_json(indent=2))
            return

        markdown = render_markdown(plan_obj)
        if stdout:
            console.print(markdown)
            return

        stem = plan_stem(request_text)
        out_path = _write_plan(repo, config.output.output_dir, stem, markdown, dry_run)
        if dry_run:
            console.print(
                f"[cyan]--dry-run[/cyan]: plan built ({len(markdown)} chars), not written."
            )
            return

        console.print(f"[green]Wrote plan[/green] -> {out_path}")
        if config.output.write_debug_json and not stub:
            debug_path = _write_debug_json(repo, config.output.output_dir, stem, plan_obj)
            console.print(f"[dim]Debug plan JSON -> {debug_path}[/dim]")
    except CodegraftError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1)


@app.command("eval")
def evaluate(
    commits: Optional[list[str]] = typer.Argument(
        None, help="Commit SHAs to evaluate. Omit to use recent history."
    ),
    repo: Path = typer.Option(
        Path("."), "--repo", help="Repository root to evaluate.",
        file_okay=False, dir_okay=True, resolve_path=True,
    ),
    last: int = typer.Option(
        0, "--last", help="Evaluate the most recent N commits (default 10 if no SHAs)."
    ),
    k: int = typer.Option(10, "--k", help="Rank cutoff for recall@k."),
    no_import_edge: bool = typer.Option(
        False, "--no-import-edge", help="Disable the import-edge ranking signal."
    ),
    no_intent_roles: bool = typer.Option(
        False, "--no-intent-roles",
        help="Disable intent-modulated role weights (frontend/backend lean).",
    ),
    ablation: bool = typer.Option(
        False, "--ablation",
        help="Score with and without the import-edge signal and show the delta.",
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit the report as JSON."),
) -> None:
    """Score ranking accuracy against real git history (recall@k, MRR). No model call.

    Each commit's subject becomes a request and its changed source files become
    the gold set; this measures how well `inspect` would have surfaced them.
    """

    import subprocess

    from codegraft.evaluation import resolve_commits, run_eval

    try:
        config = Config.load(repo)
        shas = resolve_commits(repo, commits, last)
        if not shas:
            raise CodegraftError("no commits to evaluate")
    except CodegraftError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1)
    except (subprocess.SubprocessError, OSError) as exc:
        err_console.print(
            f"[red]error:[/red] could not read git history "
            f"(is {repo} a git repository?): {exc}"
        )
        raise typer.Exit(code=1)

    try:
        if ablation:
            on = run_eval(
                repo, config, shas, k=k,
                use_import_edge=True, use_intent_roles=not no_intent_roles,
            )
            off = run_eval(
                repo, config, shas, k=k,
                use_import_edge=False, use_intent_roles=not no_intent_roles,
            )
        else:
            report = run_eval(
                repo, config, shas, k=k,
                use_import_edge=not no_import_edge,
                use_intent_roles=not no_intent_roles,
            )
    except (subprocess.SubprocessError, OSError) as exc:
        err_console.print(f"[red]error:[/red] git failed while evaluating: {exc}")
        raise typer.Exit(code=1)

    if ablation:
        if as_json:
            typer.echo(_eval_json(on, off))
            return
        _print_eval_report(on)
        _print_ablation_delta(on, off)
    else:
        if as_json:
            typer.echo(_eval_json(report))
            return
        _print_eval_report(report)


def _print_eval_report(report) -> None:
    """Render an EvalReport as a per-commit table plus aggregates."""

    from rich.table import Table

    console.print(BANNER)
    edge = "on" if report.use_import_edge else "off"
    intent = "on" if report.use_intent_roles else "off"
    table = Table(
        title=f"Ranking eval  (k={report.k}, import-edge {edge}, intent-roles {intent})"
    )
    table.add_column("#", justify="right")
    table.add_column("Commit")
    table.add_column(f"Recall@{report.k}", justify="right")
    table.add_column("1st", justify="right")
    table.add_column("Found/Gold", justify="right")
    table.add_column("Subject", overflow="fold")
    for i, c in enumerate(report.cases, 1):
        if not c.evaluable:
            table.add_row(str(i), c.sha[:7], "[dim]—[/dim]", "—", "0/0",
                          f"[dim]{c.subject}  (no source files)[/dim]")
            continue
        rank = str(c.first_rank) if c.first_rank else "—"
        recall = f"{c.recall_at_k:.2f}"
        table.add_row(str(i), c.sha[:7], recall, rank,
                      f"{c.found}/{c.gold_total}", c.subject)
    console.print(table)

    scored = report.scored
    console.print(
        f"[bold]{len(scored)}[/bold] scored / {len(report.cases)} commits   "
        f"[dim]mean[/dim] Recall@{report.k}=[green]{report.mean_recall_at_k:.3f}[/green]   "
        f"MRR=[green]{report.mean_reciprocal_rank:.3f}[/green]"
    )


def _print_ablation_delta(on, off) -> None:
    """Print the with/without-import-edge comparison — the headline ablation."""

    d_recall = on.mean_recall_at_k - off.mean_recall_at_k
    d_mrr = on.mean_reciprocal_rank - off.mean_reciprocal_rank
    console.print(
        f"\n[bold]Import-edge ablation[/bold] (k={on.k}, {len(on.scored)} scored):\n"
        f"  with    edge:  Recall@{on.k}=[green]{on.mean_recall_at_k:.3f}[/green]  "
        f"MRR=[green]{on.mean_reciprocal_rank:.3f}[/green]\n"
        f"  without edge:  Recall@{off.k}={off.mean_recall_at_k:.3f}  "
        f"MRR={off.mean_reciprocal_rank:.3f}\n"
        f"  [bold]delta[/bold]:        Recall@{on.k}=[cyan]{d_recall:+.3f}[/cyan]  "
        f"MRR=[cyan]{d_mrr:+.3f}[/cyan]"
    )


def _eval_json(report, ablation_off=None) -> str:
    """Serialize one or two EvalReports (the second is the ablation-off run)."""

    import json
    from dataclasses import asdict

    def as_dict(rep) -> dict:
        return {
            "k": rep.k,
            "use_import_edge": rep.use_import_edge,
            "use_intent_roles": rep.use_intent_roles,
            "mean_recall_at_k": rep.mean_recall_at_k,
            "mean_reciprocal_rank": rep.mean_reciprocal_rank,
            "scored": len(rep.scored),
            "commits": len(rep.cases),
            "cases": [asdict(c) for c in rep.cases],
        }

    payload: dict = {"report": as_dict(report)}
    if ablation_off is not None:
        payload["ablation_off"] = as_dict(ablation_off)
        payload["delta"] = {
            "mean_recall_at_k": report.mean_recall_at_k - ablation_off.mean_recall_at_k,
            "mean_reciprocal_rank": report.mean_reciprocal_rank
            - ablation_off.mean_reciprocal_rank,
        }
    return json.dumps(payload, indent=2)


def _read_request(
    request: Optional[str], request_file: Optional[Path], *, required: bool
) -> Optional[str]:
    """Resolve the feature request from an argument or a file.

    A file (when given) wins over the positional argument. Returns None when
    nothing is supplied and *required* is False (summary-only inspect).
    """

    if request_file is not None:
        text = request_file.read_text(encoding="utf-8").strip()
        if not text:
            raise CodegraftError(f"request file {request_file} is empty")
        return text
    if request and request.strip():
        return request.strip()
    if required:
        raise CodegraftError("provide a feature request argument or --request-file")
    return None


def _write_plan(
    repo: Path, output_dir: str, stem: str, markdown: str, dry_run: bool
) -> Path:
    plans_dir = repo / output_dir
    out_path = plans_dir / f"{stem}.md"
    if not dry_run:
        plans_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")
    return out_path


def _write_debug_json(repo: Path, output_dir: str, stem: str, plan_obj) -> Path:
    """Write the raw plan object to plans/_debug/<stem>.plan.json for transparency."""

    debug_dir = repo / output_dir / "_debug"
    debug_dir.mkdir(parents=True, exist_ok=True)
    debug_path = debug_dir / f"{stem}.plan.json"
    debug_path.write_text(plan_obj.model_dump_json(indent=2), encoding="utf-8")
    return debug_path


if __name__ == "__main__":
    app()
