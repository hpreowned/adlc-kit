import json

from adlc.scorecard import render_md, md_to_html
from harness.scorecard import agreement, summarise, sparkline


def _rec(task, arm, run, tokens, score, model="m1", behind=0):
    return {"run_id": f"{task}__{arm}__r{run}", "task": task, "arm": arm, "run": run, "category": "trace", "languages": ["python"],
            "prompt_tokens": tokens, "input_tokens": tokens, "output_tokens": 100, "model_calls": 3, "premium_requests": 1, "wall_ms": 5000, "api_duration_ms": 4000,
            "turns": 2, "bytes_read": 1000, "judge_score": score, "models": [model], "copilot_version": "1.0.105", "freshness_behind": behind}


def test_summarise_medians_and_correctness():
    s = summarise([_rec("t", "a", 1, 100, 2), _rec("t", "a", 2, 300, 1), _rec("t", "a", 3, 200, 2)])
    assert s["input_tokens"]["p50"] == 200 and s["correctness"] == 5 / 6 and s["models"] == ["m1"]


def test_render_has_sections_and_footnote(tmp_path):
    recs = [_rec("t1", a, r, 1000 * (i + 1), 2) for i, a in enumerate(["baseline", "graphify"]) for r in (1, 2, 3)]
    md = render_md(recs, {"n": 4, "exact": 0.75, "within_1": 1.0}, [])
    assert "## By arm" in md and "KB currency" in md and "Judge/human agreement" in md and "#1582" in md
    assert "| baseline | 3 |" in md
    h = md_to_html(md)
    assert h.startswith("<!doctype html>") and "<table>" in h


def test_agreement_parses_sheet():
    md = "judge: 2  ·  human: 2\njudge: 1  ·  human: 2\njudge: 0  ·  human: 2\n"
    a = agreement(md, [])
    assert a["n"] == 3 and abs(a["exact"] - 1 / 3) < 1e-9 and abs(a["within_1"] - 2 / 3) < 1e-9


def test_sparkline():
    assert len(sparkline([1, 2, 3, 4])) == 4 and sparkline([]) == ""


def test_regress_trend_row_flags_pilot_median():
    from adlc.regress import trend_row
    recs = [_rec("t", "graphify", r, 1000, 2) for r in (1, 2, 3)]
    row = trend_row(recs, "graphify", {"input_tokens_p50": 800, "correctness": 1.0})
    assert row["runs"] == 3 and row["input_tokens_p50"] == 1000 and row["pilot_median_input_tokens_p50"] == 800
    assert row["graphify"] == "0.9.97" and len(row["serena"]) == 12


def test_aggregate_renders_three_repos(tmp_path):
    from adlc.scorecard import render_aggregate
    for i, repo in enumerate(("kestrel-services", "kestrel-web", "kestrel-ops")):
        d = tmp_path / repo
        d.mkdir()
        rows = [{"at": "2026-10-30T00:00:00+00:00", "arm": "graphify", "runs": 15, "input_tokens_p50": 1000 + 100 * i, "model_calls_p50": 4,
                 "wall_ms_p50": 30000, "correctness": 0.9, "pilot_median_input_tokens_p50": 1000, "graphify": "0.9.97", "serena": "ede329aaf0c8"}]
        rows.append({**rows[0], "input_tokens_p50": 1300 if repo == "kestrel-ops" else 1000})
        (d / "trend.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    md = render_aggregate(tmp_path)
    assert md.count("| kestrel-") == 3 and "⚠" in md and "▁" in md or "█" in md
