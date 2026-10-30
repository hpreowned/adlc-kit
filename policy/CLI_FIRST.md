# CLI_FIRST.md — tooling ships as a CLI; MCP needs a written justification

## The rule
Every capability the kit gives an agent is a command-line program first: `adlc`,
`graphify`, `git`, the test runners. An MCP server is added only with the justification
recorded in this file, trimmed to the smallest tool surface that does the job.

## Why (durable arguments, in order)
1. **Composability.** CLIs pipe. `adlc query --level project "…" | head`, `graphify query … --budget 400`,
   `jq` over `graph.json`. An MCP tool returns one blob the client must swallow whole.
2. **Pinnable, auditable versions.** A CLI is a package with a version and a hash in a
   lockfile (`PINS.md` is generated from it). MCP servers are processes started by the
   client with whatever is on PATH; pinning them means pinning the launcher, as we do for
   Serena (`uvx --from git+…@<commit>`), which is strictly more moving parts.
3. **Discoverability without context cost.** `--help` is read on demand. Agents are trained
   on shell usage; a new CLI costs nothing until it is invoked.
4. **Same tool for humans and CI.** The reusable workflows run exactly what a developer
   runs locally. There is no second code path.
5. **Context-window tax** — real, but client-dependent. Copilot CLI injects every enabled
   MCP tool's schema into the prompt on every turn; with 23 Serena tools that was ~8k
   tokens of tool definitions (`session.shutdown.toolDefinitionsTokens`) before any work
   happened. Trimmed to 10 it is roughly half. Other clients lazy-load schemas, so this
   argument is listed last and labelled as such.

## The one justified exception: Serena
Serena is **stateful**: it owns running language-server processes (pyright, jdtls,
csharp-ls, typescript-language-server) whose warm-up costs seconds to a minute and whose
value is precisely that they stay up across tool calls. A CLI that restarted a language
server per invocation would be unusable. It is therefore allowed as the only MCP server
in the system, with these constraints:
- pinned to a commit (`adlc/pins.json`, mirrored in `.mcp.json`);
- launched with `--context .serena/adlc-context.yml --agent-interface tools --project-from-cwd`;
- trimmed to **10 tools** (Copilot's `.mcp.json` `tools` filter did not trim at
  CLI 1.0.105, so the committed Serena context enforces it):

| Tool | Why it is in |
|---|---|
| `find_symbol` | type-aware symbol lookup across files — grep cannot do name-path queries |
| `find_referencing_symbols` | true references, not string matches |
| `find_implementations` | interface → implementations (C#/Java heavy codebases) |
| `get_symbols_overview` | file outline without reading the file |
| `get_diagnostics_for_file` | compiler-grade errors after an edit, before tests |
| `replace_symbol_body` | edit a whole symbol without line arithmetic |
| `insert_after_symbol` / `insert_before_symbol` | add members/functions at a stable anchor |
| `read_memory` / `list_memories` | the committed contract memories |

Excluded on purpose: all file read/write/shell tools (Copilot has them; duplicates cause
tool-choice thrash), all memory **write** tools (memories are contract surface, changed by
PR), `onboarding`/`activate_project`/`serena_repl`/dashboard (session management).

## Process for adding another MCP server
Open a PR against this file with: the stateful property that makes a CLI unworkable, the
tool allowlist with one line per tool, the pin, and the measured token cost. No entry here,
no server in `.mcp.json`; `adlc lint` fails on unknown servers.
