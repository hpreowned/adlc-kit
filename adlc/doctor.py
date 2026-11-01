"""`adlc doctor`: one green/red table. Verifies the contract files, the env, that pins
match the kit, that language servers are reachable, and artifact freshness."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from adlc import __version__
from adlc import contract as C
from adlc.lint import lint
from adlc.pins import load_pins
from adlc.stale import check as stale_check

GREEN, RED, YELLOW = "\033[32mOK \033[0m", "\033[31mFAIL\033[0m", "\033[33mWARN\033[0m"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""
    warn: bool = False

    def row(self) -> str:
        mark = GREEN if self.ok else (YELLOW if self.warn else RED)
        return f"  {mark}  {self.name:<34} {self.detail}"


def _ver(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (r.stdout or r.stderr).strip().splitlines()[0] if r.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return None


def _serena_ls_cached(name: str) -> bool:
    cache = Path.home() / ".serena" / "language_servers" / "static"
    return cache.exists() and any(name.lower() in p.name.lower() for p in cache.iterdir())


def ls_checks(repo: Path) -> list[Check]:
    out: list[Check] = []
    py = repo / ".serena" / "project.yml"
    if not py.exists():
        return out
    import yaml
    langs = (yaml.safe_load(py.read_text()) or {}).get("language_servers", [])
    probes = {"python": (["pyright", "pyright-langserver", "basedpyright"], "pyright"),
              "typescript": (["typescript-language-server"], "typescript"),
              "java": (["jdtls"], "jdtls"), "csharp": (["Microsoft.CodeAnalysis.LanguageServer", "csharp-ls"], "csharp")}
    for lang in langs:
        bins, cache_key = probes.get(lang, ([], lang))
        on_path = next((b for b in bins if shutil.which(b)), None)
        cached = _serena_ls_cached(cache_key)
        ok = bool(on_path or cached)
        where = f"PATH:{on_path}" if on_path else ("serena-cache" if cached else "not found (Serena downloads on first use)")
        out.append(Check(f"language server: {lang}", ok, where, warn=not ok))
        if lang == "csharp":
            # Roslyn LS 5.5 needs the .NET 10 *runtime*; with it missing Serena fails to
            # initialise the whole project, not just C# (found 2026-11-01 on kestrel-services).
            r = subprocess.run(["dotnet", "--list-runtimes"], capture_output=True, text=True) if shutil.which("dotnet") else None
            has10 = bool(r and r.returncode == 0 and any(l.startswith("Microsoft.NETCore.App 10.") for l in r.stdout.splitlines()))
            out.append(Check(".NET 10 runtime (Roslyn LS)", has10, "found" if has10 else "missing — Serena will fail to start for this repo: dotnet-install.sh --channel 10.0 --runtime dotnet"))
    return out


def run_checks(repo: Path) -> list[Check]:
    pins = load_pins()
    checks: list[Check] = []
    fails, warns = lint(repo)
    checks.append(Check("contract lint", not fails, "; ".join(fails) if fails else f"{len(warns)} warning(s)"))
    for w in warns:
        checks.append(Check("  lint warning", True, w, warn=True))
    try:
        c = C.load(repo)
    except C.ContractError as e:
        checks.append(Check("AGENTS.md adlc block", False, str(e)))
        return checks
    checks.append(Check("AGENTS.md adlc block", True, f"schema {c.schema}, kit {c.kit}, context {','.join(c.context)}"))
    tok = bool(os.environ.get("COPILOT_GITHUB_TOKEN"))
    checks.append(Check("env COPILOT_GITHUB_TOKEN", tok, "present" if tok else "missing (headless runs need it)", warn=not tok))
    be = os.environ.get("GRAPHIFY_BACKEND", "<unset>")
    checks.append(Check("env GRAPHIFY_BACKEND", be in ("none", "<unset>"), be, warn=(be == "<unset>")))
    keys = [k for k in ("GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY", "KIMI_API_KEY") if os.environ.get(k)]
    checks.append(Check("no LLM API keys in env", not keys, ", ".join(keys) if keys else "clean", warn=bool(keys)))
    gv = _ver(["graphify", "--version"]) or ""
    try:
        from importlib.metadata import version
        gv = version("graphifyy")
    except Exception:  # pragma: no cover
        pass
    checks.append(Check("graphify version == pin", gv == pins["graphify"]["version"], f"{gv or 'missing'} vs {pins['graphify']['version']}"))
    cv = _ver(["copilot", "--version"]) or ""
    want = pins["copilot_cli"]["version"]
    checks.append(Check("copilot CLI version == pin", want in cv, f"{cv or 'missing'} vs {want}", warn=bool(cv) and want not in cv))
    checks.append(Check("uvx available (Serena launcher)", bool(shutil.which("uvx")), shutil.which("uvx") or "missing"))
    if "serena" in c.context:
        from adlc.init import mcp_paths
        paths = mcp_paths(repo)
        pinned = all(m.exists() and pins["serena"]["commit"] in m.read_text() for m in paths)
        where = ", ".join(str(m.relative_to(repo)) for m in paths)
        checks.append(Check(".mcp.json serena pin (root + services)", pinned, f"{pins['serena']['commit'][:12]} in {where}"))
        checks += ls_checks(repo)
    s = stale_check(repo, c.artifact, c.stale_threshold)
    if not s.exists:
        checks.append(Check("artifact freshness", True, "not built yet — run `adlc baseline`", warn=True))
    else:
        checks.append(Check("artifact freshness", s.exit_code < 2, s.line(), warn=(s.exit_code == 1)))
    for rel in (".github/workflows/adlc.yml", "renovate.json", ".graphifyrc"):
        checks.append(Check(rel, (repo / rel).exists(), ""))
    return checks


def add_parser(sub) -> None:
    p = sub.add_parser("doctor", help="verify contract files, env, pins, language servers")
    p.add_argument("--repo", default=".")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=run)


def run(args) -> int:
    repo = Path(args.repo).resolve()
    checks = run_checks(repo)
    if args.json:
        print(json.dumps([c.__dict__ for c in checks], indent=2))
    else:
        print(f"adlc doctor — {repo.name} (kit {__version__})")
        for c in checks:
            print(c.row())
    hard = [c for c in checks if not c.ok and not c.warn]
    print("doctor: " + ("all green" if not hard else f"{len(hard)} failure(s)"))
    return 1 if hard else 0
