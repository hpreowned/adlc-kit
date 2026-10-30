import subprocess
from pathlib import Path

import pytest

AGENTS = """# AGENTS.md

Build: `make test`. Docs live in `docs/`.

```yaml
adlc:
  schema: 1
  context: [graphify, serena]
  artifact: graphify-out/graph.json
  sensitive: [migrations/]
  freshness: two-tier
  kit: 0.1.0
```
"""


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.email", "t@example.com")
    git(r, "config", "user.name", "t")
    (r / "README.md").write_text("hi\n")
    (r / "docs").mkdir()
    (r / "AGENTS.md").write_text(AGENTS)
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "init")
    return r


def commit(repo: Path, name: str) -> str:
    (repo / name).write_text(name)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", name)
    return git(repo, "rev-parse", "HEAD")
