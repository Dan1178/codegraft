"""Lightweight codebase characterization.

No language server, no AST — just extension mapping, well-known filenames, and a
shallow read of manifests for framework hints. Enough to tell a planning model
"this is a Python FastAPI service with a tests/ dir", which is all it needs.
"""

from __future__ import annotations

from pathlib import Path

# Extension → language. Lowercased extension without the dot.
_EXT_LANG: dict[str, str] = {
    "py": "Python",
    "pyi": "Python",
    "js": "JavaScript",
    "jsx": "JavaScript",
    "mjs": "JavaScript",
    "cjs": "JavaScript",
    "ts": "TypeScript",
    "tsx": "TypeScript",
    "go": "Go",
    "rs": "Rust",
    "java": "Java",
    "kt": "Kotlin",
    "rb": "Ruby",
    "php": "PHP",
    "cs": "C#",
    "cpp": "C++",
    "cc": "C++",
    "c": "C",
    "h": "C/C++ header",
    "hpp": "C++ header",
    "swift": "Swift",
    "scala": "Scala",
    "sh": "Shell",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "scss": "CSS",
    "vue": "Vue",
    "svelte": "Svelte",
    "md": "Markdown",
    "yml": "YAML",
    "yaml": "YAML",
    "toml": "TOML",
    "json": "JSON",
}

# Well-known filenames → language (extensionless or special).
_FILENAME_LANG: dict[str, str] = {
    "Dockerfile": "Dockerfile",
    "Makefile": "Makefile",
    "pyproject.toml": "Python",
    "package.json": "JavaScript",
    "go.mod": "Go",
    "Cargo.toml": "Rust",
    "Gemfile": "Ruby",
    "composer.json": "PHP",
    "pom.xml": "Java",
}

_MANIFEST_FILES = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "Pipfile",
    "package.json",
    "go.mod",
    "Cargo.toml",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Gemfile",
    "composer.json",
    "Dockerfile",
    "Makefile",
}

# Entry-point filenames (basename match).
_ENTRY_BASENAMES = {
    "main.py",
    "app.py",
    "__main__.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "index.js",
    "index.ts",
    "server.js",
    "server.ts",
    "app.js",
    "app.ts",
    "main.go",
    "main.rs",
}

# Substring → framework. Checked against manifest *contents* (dependency names).
_FRAMEWORK_MARKERS: dict[str, str] = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "starlette": "Starlette",
    "sqlalchemy": "SQLAlchemy",
    "pydantic": "Pydantic",
    "express": "Express",
    "next": "Next.js",
    "react": "React",
    "vue": "Vue",
    "svelte": "Svelte",
    "nestjs": "NestJS",
    "@nestjs": "NestJS",
    "gin-gonic": "Gin",
    "fiber": "Fiber",
    "rails": "Rails",
    "laravel": "Laravel",
    "spring-boot": "Spring Boot",
    "actix": "Actix",
    "axum": "Axum",
}


def _ext(path: str) -> str:
    name = path.rsplit("/", 1)[-1]
    if "." in name:
        return name.rsplit(".", 1)[-1].lower()
    return ""


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def language_of(path: str) -> str | None:
    """Best-guess language for a single path, or None if unknown."""

    base = _basename(path)
    if base in _FILENAME_LANG:
        return _FILENAME_LANG[base]
    return _EXT_LANG.get(_ext(path))


def language_mix(paths: list[str]) -> dict[str, int]:
    """Count files per detected language, sorted high-to-low."""

    counts: dict[str, int] = {}
    for path in paths:
        lang = language_of(path)
        if lang and lang not in {"Markdown", "JSON", "YAML", "TOML"}:
            counts[lang] = counts.get(lang, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def primary_language(mix: dict[str, int]) -> str:
    return next(iter(mix), "")


def find_manifests(paths: list[str]) -> list[str]:
    """Manifest files, preferring shallower paths (root manifests matter most)."""

    found = [p for p in paths if _basename(p) in _MANIFEST_FILES]
    return sorted(found, key=lambda p: (p.count("/"), p))


def find_entry_points(paths: list[str]) -> list[str]:
    found = [p for p in paths if _basename(p) in _ENTRY_BASENAMES]
    return sorted(found, key=lambda p: (p.count("/"), p))


# JS/TS source extensions that carry `.test.`/`.spec.` test files. Kept in step
# with imports._JS_EXTS so "what counts as a test" and "what resolves as a module"
# don't drift — the omission of the `x`/`jsx` variants here used to make
# `affected_tests` and the ranking `test` signal silently ignore React component
# tests (`*.test.tsx`), the dominant test form on a TS frontend.
_JS_TS_EXTS = {"ts", "tsx", "js", "jsx", "mjs", "cjs"}


def _is_js_ts_test(base: str) -> bool:
    """True for `*.test.{ts,tsx,js,jsx,mjs,cjs}` and the `*.spec.*` variants."""

    stem, _, ext = base.rpartition(".")
    return ext in _JS_TS_EXTS and (stem.endswith(".test") or stem.endswith(".spec"))


def find_test_paths(paths: list[str]) -> list[str]:
    """Distinct top-level-ish directories/files that look like tests."""

    seen: list[str] = []
    for p in paths:
        base = _basename(p)
        segments = p.split("/")
        is_test = (
            any(seg in {"tests", "test", "__tests__", "spec"} for seg in segments)
            or base.startswith("test_")
            or base.endswith(("_test.go", "_test.py"))
            or _is_js_ts_test(base)
        )
        if is_test:
            # Record the test root directory if there is one, else the file.
            root = next(
                (
                    "/".join(segments[: i + 1])
                    for i, seg in enumerate(segments)
                    if seg in {"tests", "test", "__tests__", "spec"}
                ),
                p,
            )
            if root not in seen:
                seen.append(root)
    return sorted(seen)


def detect_frameworks(root: Path, manifests: list[str]) -> list[str]:
    """Shallow-read manifests and match dependency names to known frameworks."""

    found: list[str] = []
    for manifest in manifests:
        path = root / manifest
        try:
            text = path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        for marker, name in _FRAMEWORK_MARKERS.items():
            if marker in text and name not in found:
                found.append(name)
    return found
