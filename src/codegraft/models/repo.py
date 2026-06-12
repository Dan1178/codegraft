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
