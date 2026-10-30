"""Golden-task lint (`adlc eval --lint`) and INDEX.md generation."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml

CATEGORIES = {"locate", "literal", "trace", "archaeology", "cross-repo", "cross-project", "edit"}
LANGS = {"python", "typescript", "java", "csharp", "docs"}
REQUIRED = ("id", "repo", "category", "languages", "tier", "prompt", "expected", "rubric", "judge")
TIER_LANGS = {1: {"python", "typescript"}, 2: {"java", "csharp"}, 3: LANGS}


def load_tasks(root: Path) -> list[dict]:
    tasks = []
    for p in sorted(root.glob("*/*.yaml")):
        t = yaml.safe_load(p.read_text())
        t["_path"] = str(p)
        tasks.append(t)
    return tasks


def _files_in_expected(expected: str) -> set[str]:
    return set(re.findall(r"[\w./-]+\.(?:py|ts|tsx|java|cs|sql|md|json|yml|yaml|csv)", expected))


def grep_answers(repo_dir: Path, bait: str, expected_files: set[str]) -> bool:
    """True when a single `rg -l <bait>` already yields every file the answer names."""
    if not expected_files or not repo_dir.exists():
        return False
    r = subprocess.run(["rg", "-l", "--no-messages", bait, "."], cwd=repo_dir, capture_output=True, text=True)
    hits = {line.lstrip("./") for line in r.stdout.splitlines()}
    return all(any(h.endswith(f.split("/")[-1]) for h in hits) for f in expected_files)


def lint_task(t: dict, repos_root: Path | None) -> list[str]:
    errs = []
    for k in REQUIRED:
        if k not in t or t[k] in (None, ""):
            errs.append(f"missing {k}")
    if errs:
        return errs
    if t["category"] not in CATEGORIES:
        errs.append(f"bad category {t['category']}")
    if not set(t["languages"]) <= LANGS:
        errs.append(f"bad languages {t['languages']}")
    if t["tier"] not in TIER_LANGS or not set(t["languages"]) <= TIER_LANGS[t["tier"]]:
        errs.append(f"tier {t['tier']} does not match languages {t['languages']}")
    is_edit = t["category"] == "edit"
    if is_edit != (t["judge"] == "tests") or is_edit != bool(t.get("test_command")):
        errs.append("edit ⇔ judge: tests ⇔ test_command")
    if t["category"] == "cross-project" and not t.get("federated"):
        errs.append("cross-project tasks must set federated: true")
    if str(t["expected"]).strip().lower() in str(t["prompt"]).lower():
        errs.append("expected answer appears in the prompt")
    if t["category"] != "literal" and repos_root is not None:
        files = _files_in_expected(str(t["expected"]))
        for bait in t.get("grep_bait") or []:
            if grep_answers(repos_root / t["repo"], bait, files):
                errs.append(f"one grep for {bait!r} already yields every file in `expected` — not a context task")
    return errs


def lint_all(root: Path, repos_root: Path | None) -> tuple[list[str], list[dict]]:
    tasks = load_tasks(root)
    errs = []
    ids = [t.get("id") for t in tasks]
    for dup in {i for i in ids if ids.count(i) > 1}:
        errs.append(f"duplicate id {dup}")
    per_repo: dict[str, int] = {}
    cats = set()
    for t in tasks:
        for e in lint_task(t, repos_root):
            errs.append(f"{t['_path']}: {e}")
        per_repo[t.get("repo", "?")] = per_repo.get(t.get("repo", "?"), 0) + 1
        cats.add(t.get("category"))
    for repo, n in per_repo.items():
        if n < 10:
            errs.append(f"{repo}: only {n} tasks (need ≥ 10)")
    for c in CATEGORIES - cats:
        errs.append(f"category never used: {c}")
    return errs, tasks


def index_md(tasks: list[dict]) -> str:
    lines = ["# Golden tasks", "", f"{len(tasks)} tasks. Schema: `SCHEMA.md`. Run: `adlc eval --tier N`.", "",
             "| id | repo | category | langs | tier | judge | federated | prompt |", "|---|---|---|---|---|---|---|---|"]
    for t in sorted(tasks, key=lambda x: (x["tier"], x["repo"], x["id"])):
        prompt = " ".join(str(t["prompt"]).split())[:90]
        lines.append(f"| {t['id']} | {t['repo']} | {t['category']} | {','.join(t['languages'])} | {t['tier']} | {t['judge']} | {'yes' if t.get('federated') else ''} | {prompt} |")
    by_cat: dict[str, int] = {}
    for t in tasks:
        by_cat[t["category"]] = by_cat.get(t["category"], 0) + 1
    lines += ["", "## By category", ""] + [f"- {c}: {n}" for c, n in sorted(by_cat.items())] + [""]
    return "\n".join(lines)
