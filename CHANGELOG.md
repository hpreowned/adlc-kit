# Changelog

## Unreleased
- `adlc init --skill-profile lean|vendor` (default **lean** after the 2026-11-01 Tier 1 run: 142k vs 204k prompt tokens p50, 90 % vs 85 % correctness, graph queried 31/36 vs 19/36): kit-authored ~2 KB graphify skill (`template/github/skills/graphify-lean/SKILL.md`) at the same path as the vendor one; switching removes `references/`. New harness arm `graphify-lean` swaps it into the working copy so the cost of the 48 KB vendor skill text can be separated from the cost of the graph.
- `adlc-regress.yml`: `actions/cache@v4` on uv (tools + cache, keyed on kit ref), npm (keyed on Copilot CLI version) and `~/.serena/language_servers` (keyed on kit ref + `.serena/project.yml`). Toolchain install is paid once per kit bump, not weekly.

## 0.1.3 — 2026-11-01
- Devcontainer removed from the kit (not approved for use in this org; the pilot never ran in one). `adlc init` no longer writes `.devcontainer/`; `adlc doctor` no longer checks it; `adlc-regress.yml` installs its toolchain on a plain runner (`setup` input for the repo's own build tools) instead of a container image. `INSTALL_MINUTES.md` moves to the kit root. ADOPT.md documents the bare-machine prerequisites.

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
