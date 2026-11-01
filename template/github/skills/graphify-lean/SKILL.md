---
name: graphify
description: "Use for any question about a codebase, its architecture, file relationships, or project content — especially when graphify-out/ exists, where the question should be treated as a graphify query first. Queries a prebuilt code knowledge graph (query / path / explain)."
---

# /graphify — lean profile (ADLC)

This repo ships a prebuilt graph in `graphify-out/graph.json` (nodes = files, classes,
functions, routes, docs; edges = calls, imports, references). You never build it here.

## 1. Freshness first (kit-owned)

Run `adlc stale`. Exit 0: use the graph. Exit 1: usable, say how many commits behind.
Exit 2: run `adlc baseline --incremental` (code only, no LLM), then continue.
Never set an API key. Never run the full `/graphify .` pipeline in this session.

## 2. Ask the graph before you grep

| question shape | command |
|---|---|
| what depends on / calls / uses X; where is X; how does X relate to Y | `graphify query "<question>"` |
| the route between two things | `graphify path "<A>" "<B>"` |
| what one node is | `graphify explain "<node>"` |
| across repos (project / org) | `adlc query --level project "<question>"` or `--level org` |

Exit codes: 0 = results; 3 = no match (fall back to grep); 4 = graph missing or unreadable
(say so, then grep). Run each query once; quote the node ids and file paths it returns.

## 3. Then read only what the graph pointed at

Open the files the query cited, not the whole tree. Do not read `graphify-out/graph.json`
directly; it is large and the CLI already ranks it. Do not re-run queries with rephrased
text more than once. If the graph and the code disagree, the code wins — say so.

## 4. Answer

State the answer, then the evidence: which graph nodes, which files and lines. For edit
tasks, make the change and run the repo's tests as `AGENTS.md` describes.
