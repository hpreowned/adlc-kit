"""Markdown reports for the federated graphs (PROJECT_REPORT.md / ORG_REPORT.md)."""
from __future__ import annotations

import json
from collections import Counter, defaultdict

import networkx as nx
from networkx.readwrite import json_graph


def _label(G: nx.Graph, n: str) -> str:
    return G.nodes[n].get("label", n.split("::")[-1])


def _god_nodes(G: nx.Graph, k: int = 12) -> list[tuple[str, int]]:
    deg = sorted(((n, d) for n, d in nx.Graph(G).degree()), key=lambda x: -x[1])
    return [(n, d) for n, d in deg if not n.startswith(("ref::", "team::", "project::", "repo::"))][:k]


def _cross_repo_communities(G: nx.Graph) -> list[tuple[int, dict[str, int]]]:
    comm: dict[int, Counter] = defaultdict(Counter)
    for n, a in G.nodes(data=True):
        if "community" in a and a.get("repo"):
            comm[a["community"]][a["repo"]] += 1
    out = [(c, dict(r)) for c, r in comm.items() if len(r) >= 2]
    return sorted(out, key=lambda x: -sum(x[1].values()))


def project_report(G: nx.DiGraph, members, results, meta: dict, prev_json: str | None) -> str:
    lines = [f"# Project graph — {meta['project']}  ({meta['generated_at']})", "",
             f"- {G.number_of_nodes()} nodes · {G.number_of_edges()} edges · kit {meta['kit']}", "",
             "## Members (freshness stamps)", "| repo | commit_sha |", "|---|---|"]
    lines += [f"| {m.name} | `{m.sha[:12]}` |" for m in members]
    lines += ["", "## Cross-repo resolvers", "| resolver | edges | nodes | ambiguous |", "|---|---|---|---|"]
    lines += [f"| {r.name} | {len(r.edges)} | {len(r.nodes)} | {len(r.ambiguous)} |" for r in results]
    lines += ["", "## HTTP contracts (provider → consumers)"]
    for n, a in sorted(G.nodes(data=True), key=lambda x: x[0]):
        if a.get("kind") == "http_route":
            consumers = sorted({G.nodes[s].get("repo", "?") + ":" + (G.nodes[s].get("source_file") or _label(G, s))
                                for s, _, e in G.in_edges(n, data=True) if e.get("relation") == "consumes"})
            lines.append(f"- `{a['label']}` provided by **{a.get('provider_unit', a.get('provider_repo'))}** ← " + (", ".join(consumers) or "_no consumers found_"))
    lines += ["", "## God nodes (most connected across the project)"]
    lines += [f"{i}. `{_label(G, n)}` ({G.nodes[n].get('repo', 'org')}) — {d} edges" for i, (n, d) in enumerate(_god_nodes(G), 1)]
    lines += ["", "## Cross-repo communities (subsystems spanning ≥2 repos)"]
    for c, repos in _cross_repo_communities(G)[:15]:
        hubs = [n for n, a in G.nodes(data=True) if a.get("community") == c]
        hubs.sort(key=lambda n: -nx.Graph(G).degree(n))
        lines.append(f"- community {c}: " + ", ".join(f"{r}×{k}" for r, k in sorted(repos.items())) +
                     " — hubs: " + ", ".join(f"`{_label(G, h)}`" for h in hubs[:4]))
    amb = [x for r in results for x in r.ambiguous]
    lines += ["", f"## AMBIGUOUS — needs a human ({len(amb)})"]
    lines += [f"- [{x['resolver']}] {x.get('repo', '')}:{x.get('file', '')}" + (f":{x['line']}" if x.get('line') else "") + f" — {x['issue']}" for x in amb[:60]]
    if len(amb) > 60:
        lines.append(f"- … {len(amb) - 60} more")
    if prev_json:
        try:
            from graphify.analyze import graph_diff
            prev = json_graph.node_link_graph(json.loads(prev_json), edges="links", directed=True)
            diff = graph_diff(prev, G)
            lines += ["", "## Diff vs previous build", f"- {diff.get('summary', '')}"]
        except Exception as e:  # pragma: no cover
            lines += ["", f"## Diff vs previous build", f"- unavailable: {e}"]
    return "\n".join(lines) + "\n"


def org_report(O: nx.DiGraph, meta: dict) -> str:
    lines = [f"# Org graph  ({meta['generated_at']})", "", f"- {meta['nodes']} nodes · {meta['edges']} edges · projects: " +
             ", ".join(f"{p} @ {v}" for p, v in meta["projects"].items()), "",
             "## Team ↔ project ↔ service dependency table", "| team | owns (repo / dir) | project | contracts its repos consume |", "|---|---|---|---|"]
    for t, a in sorted(O.nodes(data=True)):
        if a.get("kind") != "team":
            continue
        owns = sorted(_label(O, v) for _, v, e in O.out_edges(t, data=True) if e.get("relation") == "owns")
        projects = sorted(_label(O, v) for _, v, e in O.out_edges(t, data=True) if e.get("relation") == "works_on")
        repos = {v for _, v, e in O.out_edges(t, data=True) if e.get("relation") == "owns" and O.nodes[v].get("kind") == "repo"}
        units = repos | {v for _, v, e in O.out_edges(t, data=True) if e.get("relation") == "owns" and O.nodes[v].get("kind") == "service_dir"}
        consumes = sorted({_label(O, c) for r in units for _, c, e in O.out_edges(r, data=True) if e.get("relation") == "consumes"})
        lines.append(f"| {a['label']} | {', '.join(owns) or '—'} | {', '.join(projects) or '—'} | {', '.join(consumes) or '—'} |")
    lines += ["", "## Contracts and who depends on them", "| contract | provider | consumers |", "|---|---|---|"]
    for n, a in sorted(O.nodes(data=True)):
        if a.get("kind") in ("http_route", "package"):
            cons = sorted(_label(O, u) for u, _, e in O.in_edges(n, data=True) if e.get("relation") in ("consumes", "imports"))
            lines.append(f"| `{a['label']}` | {a.get('provider_unit', a.get('provider_repo', '?'))} | {', '.join(cons) or '—'} |")
    lines += ["", "## Cross-repo subsystems (from project-level Leiden communities)"]
    for n, a in sorted(O.nodes(data=True)):
        if a.get("kind") == "service":
            lines.append(f"- {a['label']}: {', '.join(a.get('repos', []))}")
    return "\n".join(lines) + "\n"
