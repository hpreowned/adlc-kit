# Arms

Each arm = a `COPILOT_HOME` template (copied to a per-run temp dir) + `arm.json` with the
CLI flags and repo-side toggles the runner applies. Project-level config (`.mcp.json`,
`.github/skills/graphify`) is the same committed state for every arm; arms differ only in
what is *disabled* on top of it, so "baseline" is literally the contract with the context
layer switched off.

| Arm | Home template | Flags / toggles |
|---|---|---|
| `baseline` | `settings.json` disables the `graphify` skill | `--disable-mcp-server serena`; AGENTS.md only |
| `serena` | disables `graphify` skill | Serena MCP on |
| `graphify` | empty | `--disable-mcp-server serena`; skill on; guard off |
| `graphify-guard` | empty | as graphify + `.github/hooks/adlc-guard.json` written into the working copy (non-strict) |
| `both` | empty | skill on, Serena on — only run if arms 2–4 finish and one beats baseline |
| `graphify-federated` | empty | as graphify + `adlc query --level` available (project graph fetched into the working copy) |

Nothing here is ever copied into `~/.copilot`.
