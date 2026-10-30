"""Aggregate results/*.jsonl into the scorecard tables. Pure functions; rendering lives in
adlc/scorecard.py. Every number here is reproducible from the JSONL alone."""
from __future__ import annotations

import json
import statistics as st
from collections import defaultdict
from pathlib import Path

METRICS = ("prompt_tokens", "input_tokens", "output_tokens", "cache_read_tokens", "model_calls", "premium_requests", "wall_ms", "api_duration_ms", "turns", "bytes_read")


def load_records(results: Path) -> list[dict]:
    recs = []
    for p in sorted(results.glob("*.jsonl")):
        for line in p.read_text().splitlines():
            if line.strip():
                recs.append(json.loads(line))
    return recs


def _p(vals: list[float], q: float) -> float | None:
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def summarise(recs: list[dict]) -> dict:
    out = {"n": len(recs)}
    for m in METRICS:
        vals = [r.get(m) for r in recs if isinstance(r.get(m), (int, float))]
        out[m] = {"p50": _p(vals, 0.5), "p90": _p(vals, 0.9), "cv": (st.pstdev(vals) / st.mean(vals) if len(vals) > 1 and st.mean(vals) else None)}
    scores = [r["judge_score"] for r in recs if r.get("judge_score") is not None]
    out["correctness"] = (sum(scores) / (2 * len(scores))) if scores else None
    out["scored"] = len(scores)
    edits = [r for r in recs if r.get("tests_passed") is not None]
    out["edit_pass_rate"] = (sum(1 for r in edits if r["tests_passed"]) / len(edits)) if edits else None
    out["models"] = sorted({m for r in recs for m in (r.get("models") or [])})
    out["copilot_versions"] = sorted({r.get("copilot_version") for r in recs if r.get("copilot_version")})
    beh = [r.get("freshness_behind") for r in recs if r.get("freshness_behind") is not None]
    out["staleness_p50"], out["staleness_p95"] = _p(beh, 0.5), _p(beh, 0.95)
    out["graph_queries_p50"] = _p([r.get("graph_queries", 0) for r in recs], 0.5)
    return out


def group(recs: list[dict], keys: tuple[str, ...]) -> dict[tuple, list[dict]]:
    g: dict[tuple, list[dict]] = defaultdict(list)
    for r in recs:
        key = tuple((",".join(r[k]) if isinstance(r.get(k), list) else r.get(k)) for k in keys)
        g[key].append(r)
    return dict(g)


def per_task_table(recs: list[dict]) -> list[dict]:
    rows = []
    for (task, arm), rs in sorted(group(recs, ("task", "arm")).items()):
        s = summarise(rs)
        rows.append({"task": task, "arm": arm, "n": s["n"], "tokens_p50": s["prompt_tokens"]["p50"],
                     "calls_p50": s["model_calls"]["p50"], "wall_p50": s["wall_ms"]["p50"], "correctness": s["correctness"],
                     "tokens_cv": s["prompt_tokens"]["cv"]})
    return rows


def agreement(spotcheck_md: str, recs: list[dict]) -> dict | None:
    """Parse `judge: N · human: M` lines from a filled spot-check sheet."""
    import re
    pairs = re.findall(r"judge:\s*([012])\s*·\s*human:\s*([012])", spotcheck_md)
    if not pairs:
        return None
    exact = sum(1 for j, h in pairs if j == h)
    within1 = sum(1 for j, h in pairs if abs(int(j) - int(h)) <= 1)
    return {"n": len(pairs), "exact": exact / len(pairs), "within_1": within1 / len(pairs)}


def trend_rows(trend_path: Path) -> list[dict]:
    if not trend_path.exists():
        return []
    return [json.loads(l) for l in trend_path.read_text().splitlines() if l.strip()]


def sparkline(vals: list[float]) -> str:
    bars = "▁▂▃▄▅▆▇█"
    vals = [v for v in vals if v is not None]
    if not vals:
        return ""
    lo, hi = min(vals), max(vals)
    return "".join(bars[int((v - lo) / (hi - lo) * 7) if hi > lo else 3] for v in vals)
