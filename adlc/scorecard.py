"""`adlc scorecard`: markdown + HTML from results/*.jsonl; `--trend` sparklines from
monitor/trend.jsonl; `--spotcheck` judge/human agreement."""
from __future__ import annotations

import html
import json
from pathlib import Path

from harness.scorecard import agreement, group, invalid_records, load_records, per_task_table, sparkline, summarise, trend_rows

FOOTNOTE = ("**Metric confidence.** `prompt tokens` = input + cache_read + cache_write per session (Copilot's `input.tokenCount` alone is only the uncached slice — 15–40 tokens in practice — so it is shown separately). Tokens, model calls, turns, tool calls and API time come from Copilot CLI "
            "`events.jsonl` (`session.shutdown`, `session.usage_record`) — primary. `premium_requests` is the billing "
            "number from the same event, cross-checked against the stdout `result` event; it counts prompts × model "
            "multiplier, not model calls (github/copilot-cli#1582 documents the interactive `/usage` undercount; we do not "
            "use `/usage`). `bytes_read` is a proxy: result length of view/grep/glob/bash tool calls. Model is `auto` "
            "unless pinned; tables list every resolved model and Copilot version seen — compare within a model only. "
            "No single-run number appears anywhere: every cell is a median (p50) or p90 over ≥ 3 runs.")


def _fmt(v, kind="int"):
    if v is None:
        return "—"
    if kind == "pct":
        return f"{100 * v:.0f}%"
    if kind == "cv":
        return f"{v:.2f}"
    if kind == "ms":
        return f"{v / 1000:.1f}s"
    return f"{int(round(v)):,}"


def arm_table(recs: list[dict], by: tuple[str, ...]) -> list[str]:
    hdr = "| " + " | ".join(by) + " | n | prompt tokens p50/p90 | (uncached in p50) | out p50 | calls p50 | premium p50 | wall p50/p90 | turns p50 | bytes read p50 | correctness | edit pass | tokens CV |"
    lines = [hdr, "|" + "---|" * (hdr.count("|") - 1)]
    for key, rs in sorted(group(recs, by).items(), key=lambda kv: tuple(str(k) for k in kv[0])):
        s = summarise(rs)
        lines.append("| " + " | ".join(str(k) for k in key) + f" | {s['n']} | {_fmt(s['prompt_tokens']['p50'])}/{_fmt(s['prompt_tokens']['p90'])} | {_fmt(s['input_tokens']['p50'])} | {_fmt(s['output_tokens']['p50'])} | "
                     f"{_fmt(s['model_calls']['p50'])} | {_fmt(s['premium_requests']['p50'])} | {_fmt(s['wall_ms']['p50'], 'ms')}/{_fmt(s['wall_ms']['p90'], 'ms')} | "
                     f"{_fmt(s['turns']['p50'])} | {_fmt(s['bytes_read']['p50'])} | {_fmt(s['correctness'], 'pct')} | {_fmt(s['edit_pass_rate'], 'pct')} | {_fmt(s['prompt_tokens']['cv'], 'cv')} |")
    return lines


def render_md(recs: list[dict], spot: dict | None, trend: list[dict], invalid: list[dict] | None = None) -> str:
    L = ["# ADLC scorecard", "", f"{len(recs)} valid runs · tasks {len({r['task'] for r in recs})} · arms {sorted({r['arm'] for r in recs})}", ""]
    if invalid:
        by = {}
        for r in invalid:
            by.setdefault((r["task"], (r.get("session_error") or f"exit {r.get('exit_code')}")[:60]), []).append(r["arm"])
        L += [f"**Excluded: {len(invalid)} invalid run(s)** (Copilot did not finish cleanly; never pooled):", ""]
        L += [f"- {t} — {why} — arms {sorted(set(a))}" for (t, why), a in sorted(by.items())] + [""]
    if not recs:
        return "\n".join(L + ["_no results yet_", ""])
    L += ["## By arm", ""] + arm_table(recs, ("arm",)) + ["", "## By arm × category", ""] + arm_table(recs, ("arm", "category"))
    L += ["", "## By arm × language", ""] + arm_table(recs, ("arm", "languages")) + ["", "## By arm × resolved model", ""] + arm_table(recs, ("arm", "models"))
    L += ["", "## KB currency (artifact staleness at query time, commits behind HEAD)", "", "| arm | p50 | p95 | graph queries p50 |", "|---|---|---|---|"]
    for (arm,), rs in sorted(group(recs, ("arm",)).items()):
        s = summarise(rs)
        L.append(f"| {arm} | {_fmt(s['staleness_p50'])} | {_fmt(s['staleness_p95'])} | {_fmt(s['graph_queries_p50'])} |")
    L += ["", "## Per task", "", "| task | arm | n | tokens p50 | calls p50 | wall p50 | correctness | tokens CV |", "|---|---|---|---|---|---|---|---|"]
    for r in per_task_table(recs):
        L.append(f"| {r['task']} | {r['arm']} | {r['n']} | {_fmt(r['tokens_p50'])} | {_fmt(r['calls_p50'])} | {_fmt(r['wall_p50'], 'ms')} | {_fmt(r['correctness'], 'pct')} | {_fmt(r['tokens_cv'], 'cv')} |")
    s = summarise(recs)
    L += ["", f"Models seen: {', '.join(s['models']) or '—'} · Copilot versions: {', '.join(s['copilot_versions']) or '—'}"]
    if spot:
        L += ["", f"**Judge/human agreement** (n={spot['n']}): exact {_fmt(spot['exact'], 'pct')}, within one point {_fmt(spot['within_1'], 'pct')}."]
    if trend:
        L += ["", "## Trend (regress runs)", "", "| metric | sparkline | last | pilot median | drift |", "|---|---|---|---|---|"]
        for m in ("prompt_tokens_p50", "model_calls_p50", "wall_ms_p50", "correctness"):
            vals = [t.get(m) for t in trend]
            last, base = vals[-1], trend[0].get("pilot_median_" + m) or vals[0]
            drift = ((last - base) / base) if (last is not None and base) else None
            flag = " ⚠ >15% (placeholder threshold)" if drift is not None and abs(drift) > 0.15 else ""
            L.append(f"| {m} | {sparkline(vals)} | {_fmt(last)} | {_fmt(base)} | {('%+.0f%%' % (100 * drift)) if drift is not None else '—'}{flag} |")
    L += ["", "---", "", FOOTNOTE, ""]
    return "\n".join(L)


def md_to_html(md: str) -> str:
    rows = []
    for line in md.splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if set("".join(cells)) <= {"-", ""}:
                continue
            rows.append("<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in cells) + "</tr>")
        elif line.startswith("#"):
            lvl = len(line) - len(line.lstrip("#"))
            rows.append(f"<h{lvl}>{html.escape(line.lstrip('# '))}</h{lvl}>")
        elif line.strip():
            rows.append(f"<p>{html.escape(line)}</p>")
    body = "\n".join(rows).replace("</tr>\n<h", "</tr></table>\n<h").replace("</tr>\n<p", "</tr></table>\n<p")
    body = body.replace("<tr>", "<table><tr>", 1) if "<tr>" in body else body
    import re
    body = re.sub(r"(</h\d>|</p>)\n<tr>", r"\1\n<table><tr>", body)
    return f"<!doctype html><meta charset='utf-8'><title>ADLC scorecard</title><style>body{{font:14px system-ui;max-width:1200px;margin:2rem auto}}table{{border-collapse:collapse;margin:1rem 0}}td{{border:1px solid #ccc;padding:3px 8px;font-variant-numeric:tabular-nums}}</style>{body}</table>"


def add_parser(sub) -> None:
    p = sub.add_parser("scorecard", help="render the scorecard from results JSONL")
    p.add_argument("--results", default="results")
    p.add_argument("--out", default=None)
    p.add_argument("--html", default=None)
    p.add_argument("--trend", action="store_true", help="include monitor/trend.jsonl sparklines")
    p.add_argument("--trend-file", default="monitor/trend.jsonl")
    p.add_argument("--spotcheck", default=None, help="filled spot-check sheet to compute agreement")
    p.add_argument("--aggregate", default=None, metavar="DIR", help="org mode: DIR/<repo>/trend.jsonl → one cross-repo table")
    p.set_defaults(func=run)


def render_aggregate(root: Path) -> str:
    L = ["# ADLC org scorecard (cross-repo trends)", "", "| repo | arm | last run | runs | tokens p50 | calls p50 | wall p50 | correctness | drift vs pilot | pins |", "|---|---|---|---|---|---|---|---|---|---|"]
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        rows = trend_rows(d / "trend.jsonl")
        if not rows:
            L.append(f"| {d.name} | — | no trend uploaded | | | | | | | |")
            continue
        t = rows[-1]
        tok = t.get("prompt_tokens_p50", t.get("input_tokens_p50"))
        base = t.get("pilot_median_prompt_tokens_p50") or t.get("pilot_median_input_tokens_p50") or rows[0].get("prompt_tokens_p50")
        drift = ((tok - base) / base) if (base and tok is not None) else None
        flag = (" ⚠" if drift is not None and abs(drift) > 0.15 else "") + (" (dry-run)" if t.get("dry_run") else "")
        L.append(f"| {d.name} | {t.get('arm')} | {t.get('at', '')[:10]} | {t.get('runs')} | {_fmt(tok)} | {_fmt(t.get('model_calls_p50'))} | "
                 f"{_fmt(t.get('wall_ms_p50'), 'ms')} | {_fmt(t.get('correctness'), 'pct')} | {('%+.0f%%' % (100 * drift)) if drift is not None else '—'}{flag} | graphify {t.get('graphify')} · serena {t.get('serena')} |")
    L += ["", "Sparklines (tokens p50 over time):", ""]
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        rows = trend_rows(d / "trend.jsonl")
        if rows:
            L.append(f"- {d.name}: {sparkline([r.get('prompt_tokens_p50', r.get('input_tokens_p50')) for r in rows])}")
    return "\n".join(L) + "\n"


def run(args) -> int:
    if args.aggregate:
        md = render_aggregate(Path(args.aggregate))
        if args.out:
            Path(args.out).write_text(md); print(f"wrote {args.out}")
        else:
            print(md)
        if args.html:
            Path(args.html).write_text(md_to_html(md))
        return 0
    results = Path(args.results)
    recs = load_records(results)
    invalid = invalid_records(results)
    spot = agreement(Path(args.spotcheck).read_text(), recs) if args.spotcheck and Path(args.spotcheck).exists() else None
    trend = trend_rows(Path(args.trend_file)) if args.trend else []
    md = render_md(recs, spot, trend, invalid)
    if args.out:
        Path(args.out).write_text(md)
        print(f"wrote {args.out}")
    else:
        print(md)
    if args.html:
        Path(args.html).write_text(md_to_html(md))
        print(f"wrote {args.html}")
    return 0
