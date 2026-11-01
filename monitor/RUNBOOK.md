# monitor/RUNBOOK.md — operating the ADLC layer

## Add a golden task
1. Copy any `harness/tasks/<repo>/*.yaml`, give it the next id, fill every key per `harness/tasks/SCHEMA.md`.
2. `adlc eval --lint --repos <dir with the repos>` — fix what it reports (a task one grep answers is rejected unless `category: literal`).
3. Run it once per arm: `adlc eval --task <id> --runs 3 --arms baseline,graphify`. Check `results/spotcheck.md`.
4. If it belongs in the weekly smoke set, add the id to `monitor/smoke.yml` (keep it at 5).

## Re-baseline a repo
- Normal: merge to main → `adlc-baseline` workflow rebuilds, stamps, commits `graphify-out/` (+ `.serena/memories/`) and dispatches the project repo.
- By hand (incident, CI down): `GRAPHIFY_BACKEND=none adlc baseline` in the repo, commit the artifact. Docs-only repos with a skill-built graph are stamp-only; refresh their semantic pass with `/graphify .` inside a Copilot session.
- Check: `adlc stale` → exit 0. Project/org: `adlc stale --level project|org`.

## Bump a tool
Renovate opens the PR (preset `monitor/renovate-preset.json`): graphify (pyproject), Serena commit (`.mcp.json`), kit ref (workflow). `adlc-regress` is the required check.
1. Read the new `monitor/trend.jsonl` row vs `pilot_median_*`. >15 % worse on tokens or correctness (placeholder threshold, revisit after one quarter of data) → do not merge; open an issue with the row.
2. Copilot CLI is not Renovate-managed: bump `copilot_cli.version` in `adlc/pins.json`, bump the version in `adlc-regress.yml`'s install step AND its `adlc-npm-…-copilot-<version>` cache key, run `adlc eval --tier 1 --runs 3`, re-verify `harness/EVENTS_SCHEMA.md` against a fresh `events.jsonl` (fields have moved before).
3. After merge, `adlc pins` regenerates `PINS.md`; tag the kit; consuming repos pick the tag up via Renovate.

## Read the trend
`adlc scorecard --trend` prints sparklines per metric with last value, pilot median and drift. Rows carry the graphify/serena pins and the Copilot versions seen, so a jump lines up with a bump. The org aggregator (`org/.github-private/.github/workflows/adlc-aggregate.yml`) renders one cross-repo table from every repo's uploaded `trend.jsonl`.

## When `/usage` and `events.jsonl` disagree
They measure different things. `events.jsonl` `session.shutdown.totalPremiumRequests` and the stdout `result.usage.premiumRequests` are per-prompt billing counts; `session.usage_record` rows are per-model-call (`cost` = multiplier). Interactive `/usage` is known to undercount (github/copilot-cli#1582) and is not used by the harness. If `totalPremiumRequests` ≠ the stdout `result` value for the same session, keep both in the record (`premium_requests` vs `premium_requests_stdout`), flag the run, and do not pool it with others until the CLI behaviour is understood.

## When the judge and a human disagree
`results/spotcheck.md` is 20 % of judged answers with the arm hidden. Fill `human:`; `adlc scorecard --spotcheck results/spotcheck.md` reports exact and within-one agreement. Below 70 % exact: rewrite the rubrics that disagree (they are too vague), re-judge with `adlc eval --judge-only` (planned), do not change the judge model mid-tier.

## Drift alarms
`adlc-drift` (nightly) exits nonzero when any artifact is > `stale_threshold` (default 10) commits behind, or when a project member sha / org project version is behind. First response: re-run baseline/federate (above); if the workflow itself is failing, the repo keeps working on a stale graph — the skill preamble tells the agent how stale it is.
