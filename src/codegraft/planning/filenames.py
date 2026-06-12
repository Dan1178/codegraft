"""Deterministic plan filenames: ``<date>-<slug>.md``.

Kept separate so both the renderer and the debug-artifact writer agree on the
exact same stem, and so it is trivially unit-testable.
"""

from __future__ import annotations

import re
from datetime import datetime

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(text: str, max_len: int = 50) -> str:
    """Turn an arbitrary feature request into a filesystem-safe slug.

    >>> slugify("Add role-based access control to admin routes!")
    'add-role-based-access-control-to-admin-routes'
    """

    slug = _SLUG_STRIP.sub("-", text.lower()).strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "plan"


def plan_stem(request: str, when: datetime | None = None) -> str:
    """Return the filename stem ``YYYY-MM-DD-<slug>`` for a request."""

    when = when or datetime.now()
    return f"{when:%Y-%m-%d}-{slugify(request)}"
