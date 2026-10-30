## Context routing (kit-owned — do not edit; `adlc init` rewrites this section)

Pick the tool by the shape of the question, not by habit:
- **Graph** (`/graphify query|path|explain`, or `adlc query --level project|org` for
  cross-repo questions): structural questions — who calls this, what breaks if this
  changes, path between two things, which subsystem/community owns it, *why* something
  exists (docs and ADRs are nodes too).
- **grep / file read**: literals — an error string, a config key, a feature flag, a
  column name, a log line. The graph will not beat grep here; do not try.
- **Serena (LSP)**: symbol-precise edits and references — rename, replace a symbol body,
  insert after a symbol, find references across files with type awareness.
- Before trusting the graph run `adlc stale`; exit 0 fresh, 1 usable, 2 rebuild first.
  On a feature branch run `adlc baseline --incremental` before structural queries.
- Levels: this repo's graph answers inside-repo questions; `--level project` answers
  "which consumer breaks"; `--level org` answers "which team/project is affected".
