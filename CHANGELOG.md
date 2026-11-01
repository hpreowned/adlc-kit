# Changelog

## Unreleased
- `adlc init --no-devcontainer` (bare-machine mode); `adlc doctor` reports a missing devcontainer as WARN, not FAIL. ADOPT.md documents the no-Docker prerequisites — the path the pilot actually ran on.

## 0.1.2 — 2026-10-30
- Harness: `session.error` captured per run; runs that did not finish cleanly are excluded from the scorecard and listed; `adlc eval` aborts on the first session error (quota exhaustion) instead of burning the matrix.

## 0.1.1 — 2026-10-30
- Edit tasks carry overlay tests (fail before / pass after the reference fix) and `setup_command`.
- `adlc eval --judge-only`, `adlc stale --all` (repo + project + org), `adlc regress --repo`, `adlc scorecard --aggregate`.
- Arm purity: the harness strips the other context's files from the working copy and filters the routing section per arm.
- Headline token metric is prompt tokens (input + cache read + cache write); Copilot's `input.tokenCount` alone is the uncached slice.
- `adlc federate` can write to an out dir (tests no longer touch the committed graph); workflow YAML fixes; PINS.md generated from uv.lock.
- No adoption-test deviations were found; this tag is a feature release, not a fix release.

## 0.1.0 — 2026-10-30
- First distributable. Schema 1.
- `adlc init|doctor|baseline|stale|lint|upgrade|pins|federate|query|eval|regress|scorecard|guard-hook`.
- Pins: graphifyy[leiden] 0.9.97, Serena ede329aa (GPL-3.0-or-later app / MIT SolidLSP — legal review flagged), Copilot CLI 1.0.105; language servers pinned transitively by the Serena commit.
- Six reusable workflows, devcontainer Dockerfile (not built in the pilot: no Docker), policy docs, 5-task smoke set, Renovate preset.
- Known limits: `.mcp.json` `tools` filter ignored by Copilot CLI 1.0.105 (Serena context file enforces the allowlist instead); Copilot `--model` pinning unavailable on the pilot account (auto, recorded per run).
