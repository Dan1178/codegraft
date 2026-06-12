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
    request: str = typer.Argument(..., help="Feature request to analyze."),
    repo: Path = typer.Option(
        Path("."), "--repo", help="Repository root to analyze.",
        file_okay=False, dir_okay=True, resolve_path=True,
    ),
) -> None:
    """Preview what codegraft considers important (no model call).

    Phase 1 placeholder: the deterministic ranking/snippet preview is implemented
    in Phase 3.
    """

    console.print(BANNER)
    console.print(
        f"[yellow]inspect[/yellow] is not implemented yet (arrives in Phase 3).\n"
        f"Request: [italic]{request}[/italic]\nRepo:    {repo}"
    )


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
    provider: Optional[str] = typer.Option(
        None, "--provider", help="Override provider (anthropic|openai)."
    ),
    model: Optional[str] = typer.Option(None, "--model", help="Override model id."),
    stdout: bool = typer.Option(
        False, "--stdout", help="Print the plan to stdout instead of a file."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Build the plan but do not write any file."
    ),
) -> None:
    """Generate an implementation plan and write it to the output directory."""

    try:
        request_text = _resolve_request(request, request_file)
        config = Config.load(repo)
        if provider:
            config.provider.name = provider
        if model:
            config.provider.model = model

        plan_obj = build_stub_plan(request_text, repo, config)
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


def _resolve_request(request: Optional[str], request_file: Optional[Path]) -> str:
    if request_file is not None:
        text = request_file.read_text(encoding="utf-8").strip()
        if not text:
            raise CodegraftError(f"request file {request_file} is empty")
        return text
    if request and request.strip():
        return request.strip()
    raise CodegraftError("provide a feature request argument or --request-file")


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
