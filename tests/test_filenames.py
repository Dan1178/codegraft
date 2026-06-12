"""Filename slug/stem tests."""

from __future__ import annotations

from datetime import datetime

from codegraft.planning.filenames import plan_stem, slugify


def test_slugify_basic() -> None:
    assert slugify("Add role-based access control to admin routes!") == (
        "add-role-based-access-control-to-admin-routes"
    )


def test_slugify_empty_falls_back() -> None:
    assert slugify("!!!") == "plan"


def test_slugify_truncates() -> None:
    assert len(slugify("x" * 200)) <= 50


def test_plan_stem_has_date_prefix() -> None:
    stem = plan_stem("Add caching", when=datetime(2026, 6, 11))
    assert stem == "2026-06-11-add-caching"
