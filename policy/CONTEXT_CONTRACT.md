# CONTEXT_CONTRACT.md — what every repo owes an agent

This is the standard. Vendors (Graphify, Serena) are implementations behind it and can
be swapped without touching this file or any consuming repo's prose.

## The contract, in one screen
1. **`AGENTS.md` at the repo root** is the single instruction source for agents. It is
   short, team-written prose: build/test/run/lint, conventions, what not to touch, where
   explanations live. Polyglot repos add one short `AGENTS.md` per service directory.
   `.github/copilot-instructions.md` must not exist (two sources drift).
2. **The fenced `adlc` block at the end of `AGENTS.md`** is the only machine-readable part:
   ```yaml
   adlc:
     schema: 1                      # contract version; `adlc upgrade` migrates
     context: [graphify, serena]    # which context implementations this repo uses
     artifact: graphify-out/graph.json
     sensitive: [migrations/, infra/]   # paths agents must not edit without a ticket
     freshness: two-tier            # see §Freshness
     kit: 0.1.0                     # kit version that last touched this repo
   ```
3. **A kit-owned CONTEXT ROUTING section** in `AGENTS.md` tells the agent which tool answers
   which shape of question (graph / grep / LSP) and to check freshness first.
4. **A committed, stamped context artifact** (`graphify-out/`) built by CI on every merge to
   main, carrying `commit_sha` and `generated_at`. Never built by hand on a laptop and
   pushed. The docs semantic pass is the one exception and runs inside a Copilot session.
5. **Project-level tool configuration only**: `.mcp.json`, `.serena/`, `.github/skills/`,
   `.graphifyrc`, `.devcontainer/`, `renovate.json`. Nothing a repo depends on lives in a
   developer's home directory.
6. **Committed Serena memories** (`.serena/memories/`) derived from the contract, with the
   same freshness stamp. Agents read them; they do not write them.
7. **CI enforces all of this** via `adlc-contract-lint` (PR), `adlc-baseline` (merge),
   `adlc-drift` (nightly), `adlc-regress` (weekly), `adlc-scorecard-upload`.

## Freshness (two-tier)
`adlc stale` compares the artifact's `commit_sha` with `HEAD`:
- exit 0 — fresh; use the graph.
- exit 1 — behind by ≤ `stale_threshold` commits (default 10); usable, agent says so.
- exit 2 — missing, unknown stamp, or beyond threshold; rebuild (`adlc baseline --incremental`).
Levels: L0 repo (per commit), L1 project (stamps every member sha), L2 org (stamps every
project version). `adlc stale --level project|org` reports drift at those levels.

## What the contract does NOT include
- Vendor names in prose. `AGENTS.md` says "the graph" and "the LSP"; the kit decides.
- Duplicates of build metadata already in pom.xml / csproj / pyproject / package.json.
- Any secret, token, or key. Auth is environment-only (`COPILOT_GITHUB_TOKEN`).

## Versioning
`adlc schema` is an integer. The kit is semver. A schema bump ships with a migration in
`adlc upgrade`; CHANGELOG.md records both. `adlc-contract-lint` warns on a schema older
than the kit default and fails on one the kit does not know.
