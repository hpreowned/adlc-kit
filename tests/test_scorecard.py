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
        rows = [{"at": "2026-10-30T00:00:00+00:00", "arm": "graphify", "runs": 15, "prompt_tokens_p50": 1000 + 100 * i, "input_tokens_p50": 1000 + 100 * i, "model_calls_p50": 4,
                 "wall_ms_p50": 30000, "correctness": 0.9, "pilot_median_prompt_tokens_p50": 1000, "graphify": "0.9.97", "serena": "ede329aaf0c8"}]
        rows.append({**rows[0], "prompt_tokens_p50": 1300 if repo == "kestrel-ops" else 1000})
        (d / "trend.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    md = render_aggregate(tmp_path)
    assert md.count("| kestrel-") == 3 and "⚠" in md and "▁" in md or "█" in md


def test_invalid_runs_are_excluded_and_listed(tmp_path):
    from harness.scorecard import load_records, invalid_records
    good = _rec("t", "baseline", 1, 100, 2); bad = {**_rec("t", "graphify", 1, 5, None), "session_error": "quota", "exit_code": 1, "answer": ""}
    (tmp_path / "x.jsonl").write_text(json.dumps(good) + "\n" + json.dumps(bad) + "\n")
    assert len(load_records(tmp_path)) == 1 and len(invalid_records(tmp_path)) == 1
    md = render_md(load_records(tmp_path), None, [], invalid_records(tmp_path))
    assert "Excluded: 1 invalid run" in md and "quota" in md



def test_eval_refuses_second_writer_on_same_out(tmp_path):
    from adlc.eval import _lock_out
    out = tmp_path / "x.jsonl"
    first = _lock_out(out)
    assert first is not None
    assert _lock_out(out) is None  # second writer refused while the first holds it
    first.close()
    assert _lock_out(out) is not None


def test_eval_resume_reruns_invalid_records(tmp_path):
    from adlc.eval import _done_runs
    out = tmp_path / "t3.jsonl"
    recs = [
        {"run_id": "a__baseline__r1", "exit_code": 0, "answer": "ok"},
        {"run_id": "a__baseline__r2", "exit_code": 1, "answer": ""},          # quota-killed
        {"run_id": "a__baseline__r3", "exit_code": 0, "answer": "x", "valid": False},
        {"run_id": "a__graphify__r1", "exit_code": 0, "answer": "", "session_error": "boom"},
    ]
    out.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
    assert _done_runs(out) == {"a__baseline__r1"}
    assert _done_runs(tmp_path / "missing.jsonl") == set()

