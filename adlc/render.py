"""Tiny `{{var}}` template renderer + language/service detection. No Jinja dependency."""
from __future__ import annotations

import re
from pathlib import Path

MARKERS = {
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "csharp": ["*.sln", "*.csproj"],
    "python": ["pyproject.toml", "requirements.txt", "setup.py"],
    "typescript": ["tsconfig.json", "package.json"],
}
SERENA_LS = {"java": "java", "csharp": "csharp", "python": "python", "typescript": "typescript"}


def render(template: str, **vars: str) -> str:
    def sub(m: re.Match) -> str:
        key = m.group(1)
        if key not in vars:
            raise KeyError(f"template variable {key!r} not provided")
        return str(vars[key])
    return re.sub(r"\{\{(\w+)\}\}", sub, template)


def _has_marker(d: Path, pats: list[str]) -> bool:
    return any(next(d.glob(p), None) is not None for p in pats)


def detect_languages(d: Path) -> list[str]:
    return [lang for lang, pats in MARKERS.items() if _has_marker(d, pats)]


def detect_services(repo: Path) -> dict[str, list[str]]:
    """Immediate subdirectories that carry their own build marker → languages."""
    out: dict[str, list[str]] = {}
    for child in sorted(repo.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name in {"node_modules", "docs", "scripts"}:
            continue
        langs = detect_languages(child)
        if langs:
            out[child.name] = langs
    return out


def repo_languages(repo: Path) -> list[str]:
    langs = set(detect_languages(repo))
    for ls in detect_services(repo).values():
        langs.update(ls)
    return sorted(langs)


def is_docs_only(repo: Path) -> bool:
    return not repo_languages(repo)
