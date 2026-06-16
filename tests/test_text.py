"""Tests for the ranking-signal focusing of long requests."""

from __future__ import annotations

from codegraft.utils.text import extract_keywords, ranking_signal, request_intent


def _intent(request: str) -> str:
    return request_intent(extract_keywords(request))


def test_intent_frontend_lean() -> None:
    assert _intent("migrate the frontend to react and typescript") == "frontend"
    assert _intent("restyle the dashboard template and css") == "frontend"


def test_intent_backend_lean() -> None:
    assert _intent("add a migration and a new schema for users") == "backend"
    assert _intent("secure the auth endpoints") == "backend"


def test_intent_none_when_ambiguous_or_absent() -> None:
    # Neither lexicon.
    assert _intent("improve logging and error handling") == "none"
    # Both lexicons hit -> deliberately unsteered.
    assert _intent("wire the react components to the api endpoints") == "none"


def test_short_request_passes_through() -> None:
    req = "add an openai provider"
    assert ranking_signal(req) == req


def test_markdown_heading_is_used() -> None:
    req = (
        "# Add role-based access control\n\n"
        "We need to restrict admin endpoints. " * 10
    )
    assert ranking_signal(req) == "Add role-based access control"


def test_long_paragraph_uses_first_sentence() -> None:
    # Must exceed the focus threshold (a single long sentence-laden paragraph).
    req = (
        "We need to add a new OpenAI provider to the system. "
        "It should implement the same provider protocol as the existing Anthropic "
        "provider, handle errors gracefully, support configuration via the toml file "
        "and environment variables, include proper tests with mocks, and follow the "
        "existing code conventions throughout the entire codebase."
    )
    assert len(req) > 240  # guard: the focusing path is actually exercised
    assert ranking_signal(req) == "We need to add a new OpenAI provider to the system."


def test_long_multiline_without_heading_uses_first_line() -> None:
    req = (
        "Implement caching for the planner\n"
        "- use an LRU cache\n"
        "- invalidate on file changes\n"
        "- add metrics and logging and tests and docs and benchmarks " * 5
    )
    assert ranking_signal(req) == "Implement caching for the planner"
