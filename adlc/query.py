"""`adlc query --level project|org "<question>"` — graphify-compatible query/path/explain
over the federated graph. Exit 0 answer · 3 ambiguous · 4 no match. The project graph is
located via --graph, $ADLC_PROJECT_GRAPH, ./graphify-out/project-graph.json (cached copy
for the skill), or the nearest org/<project>/project-graph.json."""
from __future__ import annotations

import json
import os
import re
from collections import deque
from pathlib import Path

import networkx as nx
from networkx.readwrite import json_graph

STOP = {"what", "which", "who", "does", "the", "a", "an", "of", "to", "in", "is", "are", "and", "or", "consumes",
        "consume", "calls", "call", "uses", "use", "depends", "on", "if", "changes", "change", "affected", "breaks",
        "owns", "own", "for", "with", "where", "how", "why", "do", "that", "this", "team", "teams", "repo", "repos"}


def locate(level: str, explicit: str | None) -> Path:
    name = "project-graph.json" if level == "project" else "org-graph.json"
    cands = [Path(explicit)] if explicit else []
    env = os.environ.get("ADLC_PROJECT_GRAPH" if level == "project" else "ADLC_ORG_GRAPH")
    if env:
        cands.append(Path(env))
    cands.append(Path.cwd() / "graphify-out" / name)
    for cand in [Path.cwd(), *Path.cwd().parents]:
        cands += sorted((cand / "org").glob(f"*/{name}")) if (cand / "org").exists() else []
        cands.append(cand / name)
    for c in cands:
        if c.exists():
            return c
    raise SystemExit(f"no {name} found (run `adlc federate`" + (" --level org" if level == "org" else "") + ")")


def load(path: Path) -> nx.DiGraph:
    return json_graph.node_link_graph(json.loads(path.read_text()), edges="links", directed=True)


def _text(G: nx.DiGraph, n: str) -> str:
    a = G.nodes[n]
    return " ".join(str(a.get(k, "")) for k in ("label", "source_file", "orig_id", "kind")).lower() + " " + n.lower()


def seeds_for(G: nx.DiGraph, question: str) -> list[str]:
    toks = [t for t in re.findall(r"[a-z0-9_./:{}\-]+", question.lower()) if t not in STOP and len(t) > 1]
    route = re.search(r"(/(?:api|v\d+)/[a-z0-9_./{}:\-]*)", question.lower())
    if route:
        norm = "/" + re.sub(r"\{[^}]*\}|:[a-z_]+", ":p", route.group(1)).strip("/")
        hits = [n for n in G.nodes if n.startswith("contract::") and n.lower().endswith(" " + norm)]
        if hits:
            return hits
    scored = []
    for n in G.nodes:
        t = _text(G, n)
        hits = sum(1 for k in toks if k in t)
        if hits:
            bonus = 2 if G.nodes[n].get("kind") in ("http_route", "package", "team", "repo") else 0
            scored.append((hits + bonus, G.degree(n), n))
    scored.sort(reverse=True)
    if not scored:
        return []
    best = scored[0][0]
    return [n for h, _, n in scored if h == best][:5]


CONTRACT_RELATIONS = {"consumes", "exposes", "imports", "references_file"}


def bfs(G: nx.DiGraph, seeds: list[str], depth: int) -> tuple[list[str], list[tuple]]:
    """BFS over the undirected view. Hops along contract edges (consumes/exposes/imports/
    references_file) are free, so a contract chain provider → gateway → web is followed
    end to end without inflating depth for ordinary call edges."""
    seen, order, q = set(seeds), list(seeds), deque((s, 0) for s in seeds)
    while q:
        n, d = q.popleft()
        for nb, e in list(G[n].items()) + [(u, e) for u, _, e in G.in_edges(n, data=True)]:
            free = e.get("relation") in CONTRACT_RELATIONS
            nd = d if free else d + 1
            if nd > depth or nb in seen:
                continue
            seen.add(nb); order.append(nb); q.append((nb, nd))
    edges = [(s, t, e) for s, t, e in G.edges(data=True) if s in seen and t in seen]
    return order, edges


TEST_MARKERS = ("/test/", "/tests/", ".test.", ".spec.", "Tests/", "test_", "conftest")


def contract_distance(G: nx.DiGraph, seeds: list[str]) -> dict[str, int]:
    """Directed contract chains. Downstream (who depends on the seed): predecessors via
    consumes/imports/references_file, then from a consumer file its own `exposes`
    contracts, and so on — provider → gateway → web. Upstream (what the seed depends on)
    is the mirror image and ranks after downstream (+50). Sibling contracts of a consumer
    are never visited, so the answer is not buried under unrelated routes."""
    USES = {"consumes", "imports", "references_file"}
    def walk(downstream: bool) -> dict[str, int]:
        dist = {s: 0 for s in seeds}
        q = deque(seeds)
        while q:
            n = q.popleft()
            if downstream:
                nxt = [u for u, _, e in G.in_edges(n, data=True) if e.get("relation") in USES]
                nxt += [t for _, t, e in G.out_edges(n, data=True) if e.get("relation") == "exposes"]
            else:
                nxt = [t for _, t, e in G.out_edges(n, data=True) if e.get("relation") in USES]
                nxt += [u for u, _, e in G.in_edges(n, data=True) if e.get("relation") == "exposes"]
            for nb in nxt:
                if nb not in dist:
                    dist[nb] = dist[n] + 1
                    q.append(nb)
        return dist
    down, up = walk(True), walk(False)
    out = dict(down)
    for n, d in up.items():
        out.setdefault(n, d + 50)
    return out


def order_nodes(G: nx.DiGraph, nodes: list[str], seeds: list[str], include_tests: bool) -> list[str]:
    """Seeds first, then nodes joined to a seed through contract edges (the cross-repo
    answer, nearest first), then the rest in BFS order. Test files dropped unless asked."""
    dist = contract_distance(G, seeds)
    out = [n for n in nodes if include_tests or not any(m in str(G.nodes[n].get("source_file", "")) for m in TEST_MARKERS)]
    return sorted(out, key=lambda n: (dist.get(n, 99), nodes.index(n)))


def render(G: nx.DiGraph, nodes: list[str], edges: list[tuple], budget: int) -> str:
    out = []
    keep = set(nodes)
    for n in nodes:
        a = G.nodes[n]
        out.append(f"NODE {a.get('label', n)} [repo={a.get('repo', a.get('provider_unit', a.get('provider_repo', 'org')))} kind={a.get('kind', a.get('file_type', '?'))} src={a.get('source_file', '-')} community={a.get('community', '-')}]")
    edges = sorted((x for x in edges if x[0] in keep and x[1] in keep),
                   key=lambda x: 0 if x[2].get("relation") in CONTRACT_RELATIONS else 1)
    for s, t, e in edges:
        tag = f"{e.get('confidence', 'EXTRACTED')}" + (f" via {e['resolver']}" if e.get("resolver") else "")
        out.append(f"EDGE {G.nodes[s].get('label', s)} --{e.get('relation', '?')} [{tag}]--> {G.nodes[t].get('label', t)}" + (f" at={e['at']}" if e.get("at") else ""))
    text, used = [], 0
    for line in out:
        used += len(line) // 4 + 1
        if used > budget:
            text.append(f"... truncated at --budget {budget} tokens ({len(out)} lines total)")
            break
        text.append(line)
    return "\n".join(text)


def add_parser(sub) -> None:
    p = sub.add_parser("query", help="query/path/explain over the federated graph")
    p.add_argument("question", nargs="?", default=None)
    p.add_argument("--level", choices=["project", "org"], default="project")
    p.add_argument("--graph", default=None)
    p.add_argument("--seed", action="append", default=None, help="start node (label or id); repeatable")
    p.add_argument("--depth", type=int, default=2)
    p.add_argument("--budget", type=int, default=2000)
    p.add_argument("--path", nargs=2, metavar=("A", "B"), default=None)
    p.add_argument("--explain", default=None, metavar="X")
    p.add_argument("--include-tests", action="store_true")
    p.set_defaults(func=run)


def _resolve_name(G: nx.DiGraph, name: str) -> list[str]:
    exact = [n for n in G.nodes if n == name or G.nodes[n].get("label") == name]
    if exact:
        return exact
    low = name.lower()
    return [n for n in G.nodes if low in str(G.nodes[n].get("label", "")).lower() or low in n.lower()]


def run(args) -> int:
    path = locate(args.level, args.graph)
    G = load(path)
    hdr = f"Graph: {path} ({G.number_of_nodes()} nodes, level={args.level})"
    if args.path:
        a, b = (_resolve_name(G, x) for x in args.path)
        if not a or not b:
            print(hdr + " | no node matches"); return 4
        if len(a) > 1 or len(b) > 1:
            print(hdr + " | ambiguous: " + ", ".join(a[:5] + b[:5])); return 3
        try:
            nodes = nx.shortest_path(G.to_undirected(as_view=True), a[0], b[0])
        except nx.NetworkXNoPath:
            print(hdr + " | no path"); return 4
        edges = [(s, t, e) for s, t, e in G.edges(data=True) if s in nodes and t in nodes]
        print(hdr + f" | path length {len(nodes) - 1}\n" + render(G, nodes, edges, args.budget)); return 0
    if args.explain:
        m = _resolve_name(G, args.explain)
        if not m:
            print(hdr + " | no node matches"); return 4
        if len(m) > 1:
            print(hdr + " | ambiguous:\n  " + "\n  ".join(m[:10])); return 3
        nodes, edges = bfs(G, m, 1)
        nodes = order_nodes(G, nodes, m, args.include_tests)
        print(hdr + f" | explain {G.nodes[m[0]].get('label', m[0])}\n" + render(G, nodes, edges, args.budget)); return 0
    if args.seed:
        seeds = []
        for s in args.seed:
            r = _resolve_name(G, s)
            if len(r) > 1:
                print(hdr + " | ambiguous seed: " + ", ".join(r[:10])); return 3
            seeds += r
    else:
        seeds = seeds_for(G, args.question or "")
    if not seeds:
        print(hdr + " | no node matches"); return 4
    nodes, edges = bfs(G, seeds, args.depth)
    nodes = order_nodes(G, nodes, seeds, args.include_tests)
    print(hdr + f" | seeds: {[G.nodes[s].get('label', s) for s in seeds]} | {len(nodes)} nodes\n" + render(G, nodes, edges, args.budget))
    return 0
