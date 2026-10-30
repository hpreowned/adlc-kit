"""Arm-blind judge. Receives (task, answer) only — never the arm. Copilot in -p mode with
the rubric + expected answer in context, returns 0/1/2. Edit tasks are judged by their
tests, never by the model. A StubJudge serves dry runs."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROMPT = """You are grading an answer produced by a coding assistant. Score it 0, 1 or 2 using ONLY the rubric.
Respond with a single line of JSON: {{"score": <0|1|2>, "reason": "<one sentence>"}}

QUESTION:
{prompt}

REFERENCE ANSWER (expert, hidden from the assistant):
{expected}

RUBRIC:
{rubric}

ASSISTANT ANSWER:
{answer}
"""


def parse_score(text: str) -> tuple[int | None, str]:
    m = re.search(r"\{[^{}]*\"score\"\s*:\s*([012])[^{}]*\}", text)
    if m:
        try:
            d = json.loads(m.group(0))
            return int(d["score"]), str(d.get("reason", ""))[:300]
        except (json.JSONDecodeError, KeyError, ValueError):
            pass
    m = re.search(r"\b([012])\b", text)
    return (int(m.group(1)), "unparsed") if m else (None, "unparsable judge output")


class CopilotJudge:
    def __init__(self, home_root: Path | None = None, model: str | None = None):
        self.home_root = home_root or Path(tempfile.mkdtemp(prefix="adlc-judge-"))
        self.model = model or os.environ.get("ADLC_JUDGE_MODEL")

    def score(self, task: dict, answer: str) -> tuple[int | None, str, dict]:
        home = self.home_root / "home"
        home.mkdir(parents=True, exist_ok=True)
        text = PROMPT.format(prompt=task["prompt"].strip(), expected=task["expected"].strip(), rubric=task["rubric"].strip(),
                             answer=(answer or "<no answer>").strip()[:8000])
        args = ["copilot", "-p", text, "--no-ask-user", "--trust-folder", "--output-format", "json",
                "--deny-tool", "shell", "--deny-tool", "view", "--deny-tool", "edit", "--deny-tool", "create", "--disable-builtin-mcps"]
        if self.model:
            args += ["--model", self.model]
        env = {"PATH": os.environ.get("PATH", ""), "HOME": os.environ.get("HOME", ""), "COPILOT_HOME": str(home),
               "COPILOT_GITHUB_TOKEN": os.environ.get("COPILOT_GITHUB_TOKEN", "")}
        with tempfile.TemporaryDirectory() as cwd:
            r = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=300)
        out = ""
        usage = {}
        for line in r.stdout.splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "assistant.message":
                out = (ev.get("data") or {}).get("content") or out
            if ev.get("type") == "result":
                usage = ev.get("usage") or {}
        score, reason = parse_score(out)
        return score, reason, {"judge_premium_requests": usage.get("premiumRequests"), "judge_raw": out[:500]}


class StubJudge:
    def __init__(self, score: int = 2):
        self._score = score

    def score(self, task, answer):
        return self._score, "stub", {"judge_premium_requests": 0}


def judge_record(record: dict, task: dict, judge) -> dict:
    if task.get("judge") == "tests":
        passed = record.get("tests_passed")
        record["judge_score"] = None if passed is None else (2 if passed else 0)
        record["judge_reason"] = "tests" if passed is not None else "no test result"
        return record
    score, reason, extra = judge.score(task, record.get("answer", ""))
    record["judge_score"], record["judge_reason"] = score, reason
    record.update(extra)
    return record


def spotcheck_md(records: list[dict], tasks: dict[str, dict], fraction: float = 0.2, seed: int = 7) -> str:
    """Every 1/fraction-th judged record, arm hidden, for a human to score in the margin."""
    import random
    rnd = random.Random(seed)
    judged = [r for r in records if r.get("judge_score") is not None and tasks.get(r["task"], {}).get("judge") != "tests"]
    sample = sorted(rnd.sample(judged, max(1, int(len(judged) * fraction))) if judged else [], key=lambda r: r["run_id"])
    lines = ["# Spot-check sheet (arm hidden)", "", f"{len(sample)} of {len(judged)} judged answers. Fill `human:` with 0/1/2.",
             "`adlc scorecard --spotcheck results/spotcheck.md` computes agreement.", ""]
    for r in sample:
        t = tasks[r["task"]]
        lines += [f"## {r['run_id'].split('__')[0]}  (ref: {r['run_id']})", "", "**Question**", "", t["prompt"].strip(), "",
                  "**Reference**", "", t["expected"].strip(), "", "**Rubric**", "", t["rubric"].strip(), "",
                  "**Answer**", "", "```", (r.get("answer") or "")[:3000], "```", "",
                  f"judge: {r['judge_score']}  ·  human: ___", "", "---", ""]
    return "\n".join(lines)
