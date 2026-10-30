# GUARDRAILS.md — every rule points at the code that enforces it

| # | Rule | Enforced by |
|---|---|---|
| 1 | No secrets in repos or transcripts; Copilot auth from `COPILOT_GITHUB_TOKEN` only | `harness/runner.py` builds a minimal child env; `harness/scrub.py` redacts `gh[opsu]_…`, API keys, abs paths before anything lands in `results/` |
| 2 | `GRAPHIFY_BACKEND=none` for every headless/CI build; docs semantic pass only via `/graphify` inside a Copilot session | `adlc/baseline.py::_env` forces the var and strips `*_API_KEY`; `adlc/doctor.py` warns on keys in env; `.github/workflows/adlc-baseline.yml` sets it |
| 3 | Everything pinned, by version and hash where possible; `PINS.md` generated | `adlc/pins.json` + `uv.lock` → `adlc pins`; `adlc pins --check` in kit CI; `adlc lint` fails when a repo's `.mcp.json` pin ≠ kit pin |
| 4 | Hook-guard off by default; only in its own arm | `harness/arms/graphify-guard/` is the only template that writes `.github/hooks/adlc-guard.json`; `adlc init` never does |
| 5 | No telemetry, no Graphify Cloud, no hosted MCP | `.mcp.json` template has one `local` server; `adlc lint` rejects `http`/`sse` servers and any `graphify.com` host; Serena dashboard disabled in args |
| 6 | Query log redirected per run, never `~/.cache` | `harness/runner.py` sets `GRAPHIFY_QUERY_LOG=<run dir>/queries.log`; `adlc/baseline.py` sets `GRAPHIFY_QUERY_LOG_DISABLE=1` |
| 7 | Every reported number reproducible by one target | `Makefile` (`make all`, `make tier1`, `make scorecard`); `results/*.jsonl` are the only inputs to `adlc scorecard` |
| 8 | The judge never sees the arm name | `harness/judge.py` receives `(task, answer)` only; arm is joined back by `run_id` in `harness/scorecard.py` |
| 9 | Any manual step is a kit bug | `results/adoption-test.md` logs every deviation; each one has a kit commit |
| 10 | One instruction source | `adlc lint` fails if `.github/copilot-instructions.md` exists |
| 11 | Nothing a repo depends on lives in `~` | `adlc init` writes only under the repo; `adlc doctor` reads nothing from `~` except to *warn* about LLM keys |
| 12 | Edits to `sensitive:` paths need a ticket | `adlc/lint.py` warns on diffs touching those paths without a ticket id in the commit message (PR check) |
