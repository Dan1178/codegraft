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
        markdown = render_markdown(plan_obj)

        if stdout:
            console.print(markdown)
            return

        out_path = _write_plan(repo, config.output.output_dir, request_text, markdown, dry_run)
        if dry_run:
            console.print(
                f"[cyan]--dry-run[/cyan]: plan built ({len(markdown)} chars), not written."
            )
        else:
            console.print(f"[green]Wrote plan[/green] -> {out_path}")
    except CodegraftError as exc:
        err_console.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(code=1)


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
    repo: Path, output_dir: str, request: str, markdown: str, dry_run: bool
) -> Path:
    plans_dir = repo / output_dir
    out_path = plans_dir / f"{plan_stem(request)}.md"
    if not dry_run:
        plans_dir.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    app()
