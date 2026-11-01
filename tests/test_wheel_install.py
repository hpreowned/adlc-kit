"""The kit must work as an installed wheel, not only from the source checkout.
Builds the wheel, installs it into a clean venv, onboards a scratch repo."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(shutil.which("uv") is None, reason="uv not on PATH")


def _run(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=False)


def test_wheel_installs_and_inits_a_repo(tmp_path):
    env = {**os.environ, "GRAPHIFY_BACKEND": "none", "UV_NO_PROGRESS": "1"}
    dist = tmp_path / "dist"
    r = _run(["uv", "build", "--wheel", "-q", "-o", str(dist)], ROOT, env)
    assert r.returncode == 0, r.stderr
    wheel = next(dist.glob("adlc-*.whl"))
    venv = tmp_path / "venv"
    assert _run(["uv", "venv", "-q", "-p", "3.12", str(venv)], tmp_path, env).returncode == 0
    r = _run(["uv", "pip", "install", "-q", "-p", str(venv / "bin" / "python"), str(wheel)], tmp_path, env)
    assert r.returncode == 0, r.stderr
    adlc = venv / "bin" / "adlc"

    r = _run([str(adlc), "--version"], tmp_path, env)
    assert r.returncode == 0 and "Traceback" not in r.stderr, r.stderr
    version = json.loads((ROOT / "adlc" / "pins.json").read_text())["kit"]["ref"]
    assert r.stdout.strip() == f"adlc {version.lstrip('v')}"

    repo = tmp_path / "acme"
    (repo / "src" / "acme").mkdir(parents=True)
    (repo / "src" / "acme" / "__init__.py").write_text("def add(a, b):\n    return a + b\n")
    (repo / "pyproject.toml").write_text('[project]\nname = "acme"\nversion = "0.1.0"\n')
    g = {**env, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "init"]):
        assert _run(cmd, repo, g).returncode == 0

    r = _run([str(adlc), "init", "--yes"], repo, env)
    assert r.returncode == 0 and "Traceback" not in r.stderr, r.stdout + r.stderr
    wf = (repo / ".github" / "workflows" / "adlc.yml").read_text()
    assert f"hpreowned/adlc-kit/.github/workflows/adlc-contract-lint.yml@{version}" in wf
    assert (repo / "AGENTS.md").exists() and (repo / ".github" / "skills" / "graphify" / "SKILL.md").exists()

    for sub in (["doctor"], ["lint"]):
        r = _run([str(adlc), *sub], repo, env)
        assert "Traceback" not in r.stderr, r.stderr
