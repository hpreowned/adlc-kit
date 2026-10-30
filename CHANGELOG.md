# Changelog

## 0.1.0 — 2026-10-30
- First distributable. Schema 1.
- `adlc init|doctor|baseline|stale|lint|upgrade|pins|federate|query|eval|regress|scorecard|guard-hook`.
- Pins: graphifyy[leiden] 0.9.97, Serena ede329aa (GPL-3.0-or-later app / MIT SolidLSP — legal review flagged), Copilot CLI 1.0.105; language servers pinned transitively by the Serena commit.
- Six reusable workflows, devcontainer Dockerfile (not built in the pilot: no Docker), policy docs, 5-task smoke set, Renovate preset.
- Known limits: `.mcp.json` `tools` filter ignored by Copilot CLI 1.0.105 (Serena context file enforces the allowlist instead); Copilot `--model` pinning unavailable on the pilot account (auto, recorded per run).
