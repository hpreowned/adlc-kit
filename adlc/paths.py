"""Where kit data lives, both in a source checkout and inside an installed wheel."""
from __future__ import annotations

from pathlib import Path

_HERE = Path(__file__).resolve().parent


def kit_root() -> Path:
    """Source checkout root (has pyproject.toml) or the packaged _data dir."""
    src = _HERE.parent
    if (src / "pyproject.toml").exists() and (src / "template").exists():
        return src
    return _HERE / "_data"


def template_dir() -> Path:
    return kit_root() / "template"


def harness_dir() -> Path:
    """The harness ships as a real package (imported as `harness`), so locate it by import:
    works in a source checkout, an editable install and an installed wheel alike."""
    import harness
    return Path(harness.__file__).resolve().parent


def monitor_dir() -> Path:
    return kit_root() / "monitor"


def policy_dir() -> Path:
    return kit_root() / "policy"


def repo_root(start: Path | None = None) -> Path:
    """Nearest ancestor containing .git, else the start dir."""
    p = (start or Path.cwd()).resolve()
    for cand in [p, *p.parents]:
        if (cand / ".git").exists():
            return cand
    return p
