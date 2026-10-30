> **ADLC freshness check (kit-owned).** Before answering from the graph, run
> `adlc stale`. Exit 0: use `graphify-out/graph.json` as-is. Exit 1: usable, say how many
> commits behind. Exit 2: run `adlc baseline --incremental` first (code only, no LLM).
> The docs semantic pass (`/graphify .` full pipeline) is the ONLY place an LLM touches
> this graph and it runs inside this Copilot session — never set an API key for it.
> Cross-repo questions: `adlc query --level project "<q>"` or `--level org`.
