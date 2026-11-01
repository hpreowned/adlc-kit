# ADOPT.md — make a repo agent-ready in 15 minutes

You have: a repo on GitHub, a `COPILOT_GITHUB_TOKEN` (or a `gh` login), and a machine
with `git`, `uv`, the Copilot CLI (1.0.105, see `PINS.md`) and your repo's own build
toolchain on `PATH` (JDK + Maven, .NET SDK, Node — whatever `AGENTS.md` says the tests
need). Serena fetches its pinned language servers on first start; C# additionally needs
the .NET 10 runtime. Export `GRAPHIFY_BACKEND=none`. No container, no Docker: the kit
ships none and the pilot ran without one (`INSTALL_MINUTES.md` has the measured costs).
Nothing below writes to your home directory except tool caches.

Set a timer. Every step prints what it did. If you have to deviate from this page, that
is a kit bug: note the time and what you did in `results/adoption-test.md` and file it.

## 0. Install the kit (≈1 min)
```bash
uv tool install "git+https://github.com/kestrel-freight/adlc-kit@v0.1.3"
adlc --version          # adlc 0.1.3
```

## 1. Onboard the repo (≈1 min)
```bash
cd <your-repo>
export COPILOT_GITHUB_TOKEN="$(gh auth token)"   # or paste your token into the env; never into a file
adlc init
```
It prints every file it created. It is idempotent — run it again any time.

## 2. Fill the prose in `AGENTS.md` (≈5 min, the only manual step)
Open `AGENTS.md`. Replace each `TODO` with one line: build, test, run, lint; conventions;
what not to touch; where ADRs/runbooks live. Backticked paths must exist in the repo
(the lint checks). For a path in another repo write `repo:path`. Do not edit the
section between the `adlc:routing` markers or the fenced `adlc:` block — the kit owns them.
Polyglot repo? `adlc init` also created `<service>/AGENTS.md` skeletons — fill those too.

## 3. Verify (≈1 min)
```bash
adlc doctor
```
Everything should be `OK` or `WARN`. A `FAIL` on *contract lint* means a path you typed
does not exist. "artifact freshness: not built yet" is expected — next step.

## 4. Build the context layer (≈1–3 min)
```bash
adlc baseline
adlc stale            # → [repo] FRESH … exit 0
```
`graphify-out/` and `.serena/memories/` are committed artifacts. CI rebuilds them on
every merge to `main` via `.github/workflows/adlc.yml` (already added).

## 5. Try it (≈3 min)
```bash
copilot -p "Which modules depend on <some central symbol in your repo>?" --trust-folder --allow-all-tools
```
Watch the agent use `/graphify query` for structure and Serena for symbols. Compare with
`copilot --disable-mcp-server serena -p "…"` plus `settings.json` skill off if you want
the baseline feeling; the harness does this properly: `adlc eval --dry-run` first (free),
then `adlc eval --task <id> --runs 3`.

## 6. Commit and open the PR (≈2 min)
```bash
git add -A && git commit -m "adlc init: contract layer + baseline graph"
```
The PR runs `adlc-contract-lint` as a required check. After merge, `adlc-baseline` stamps
the graph; nightly `adlc-drift` and weekly `adlc-regress` keep it honest.

## Later
- `adlc upgrade` when the kit bumps its schema (Renovate opens the PR).
- Docs-heavy repo? Run `/graphify .` once inside a Copilot session to add the semantic
  (docs) layer; `adlc baseline` will keep it and only re-stamp.
- Cross-repo questions: your project repo runs `adlc federate`; then `adlc query --level project "…"`.

Troubleshooting is in `monitor/RUNBOOK.md`. The contract itself is `policy/CONTEXT_CONTRACT.md`.
