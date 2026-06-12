"""Typed results of repository discovery.

These are the deterministic, model-free outputs of the scan stage. Paths are
always **repo-relative with forward slashes**, regardless of OS, so that ignore
matching, ranking, and prompt rendering behave identically on Windows and POSIX.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RepoFile(BaseModel):
    """A file that survived discovery, ignore, and safety filtering."""

    path: str = Field(description="Repo-relative path, forward slashes.")
    size_bytes: int = Field(description="File size in bytes.")
    tracked: bool = Field(
        default=True,
        description="Whether git tracks this file. True (assumed) in non-git fallback.",
    )


class SkippedFile(BaseModel):
    """A candidate path that was deliberately excluded, with the reason."""

    path: str = Field(description="Repo-relative path, forward slashes.")
    reason: str = Field(
        description="Why it was skipped: excluded | secret | oversized | generated | binary | unreadable."
    )


class RepoScan(BaseModel):
    """The full result of scanning a repository."""

    root: str = Field(description="Absolute path of the repository root.")
    files: list[RepoFile] = Field(
        default_factory=list, description="Files kept as analysis candidates."
    )
    skipped: list[SkippedFile] = Field(
        default_factory=list, description="Excluded paths and why."
    )
    used_git: bool = Field(
        description="True if git ls-files drove discovery, False if filesystem fallback."
    )
    truncated: bool = Field(
        default=False,
        description="True if the candidate list hit max_candidate_files and was cut.",
    )

    @property
    def file_count(self) -> int:
        return len(self.files)

    def skipped_by_reason(self) -> dict[str, int]:
        """Aggregate skip counts per reason, for summaries and `inspect`."""

        counts: dict[str, int] = {}
        for item in self.skipped:
            counts[item.reason] = counts.get(item.reason, 0) + 1
        return counts


class RepoSummary(BaseModel):
    """Compact, model-free characterization of a repository.

    This is the "what kind of codebase is this" answer that gets handed to the
    planning model alongside ranked files and snippets.
    """

    root: str = Field(description="Absolute repository root.")
    file_count: int = Field(description="Number of analysis-candidate files.")
    mode: str = Field(
        default="normal",
        description="Scale mode: normal | medium | large (drives stricter caps).",
    )
    primary_language: str = Field(
        default="", description="Best-guess primary language."
    )
    languages: dict[str, int] = Field(
        default_factory=dict, description="File count per detected language."
    )
    manifests: list[str] = Field(
        default_factory=list, description="Root/build manifest files found."
    )
    frameworks: list[str] = Field(
        default_factory=list, description="Detected frameworks/libraries."
    )
    entry_points: list[str] = Field(
        default_factory=list, description="Likely application entry-point files."
    )
    test_paths: list[str] = Field(
        default_factory=list, description="Directories/files that look like tests."
    )
    directory_tree: str = Field(
        default="", description="Compact, depth-limited directory tree."
    )


class RankedFile(BaseModel):
    """A candidate file with its relevance score and a signal breakdown.

    The `signals` map is what makes ranking *explainable* — `inspect` renders it
    so weak ranking is visible and tunable instead of a black box.
    """

    path: str = Field(description="Repo-relative path.")
    score: float = Field(description="Total relevance score (higher = more relevant).")
    signals: dict[str, float] = Field(
        default_factory=dict, description="Per-component score contributions."
    )


class Snippet(BaseModel):
    """A bounded slice of a file's content selected as planning evidence."""

    path: str = Field(description="Repo-relative path the snippet came from.")
    content: str = Field(description="The extracted snippet text.")
    line_count: int = Field(description="Number of lines in the snippet.")
    char_count: int = Field(description="Number of characters in the snippet.")
    truncated: bool = Field(
        default=False, description="True if the file was longer than the line cap."
    )
