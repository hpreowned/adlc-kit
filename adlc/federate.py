"""`adlc federate`: L1 project graph from member repo graphs (namespaced ids, four
cross-repo resolvers, re-clustered) and L2 coarse org graph from project graphs.
Pure JSON + NetworkX; `graphify.analyze.graph_diff` for diffs; no graph database."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
import yaml
from networkx.readwrite import json_graph

from adlc import __version__
from adlc.fedreport import org_report, project_report
from adlc.gitinfo import head_sha
from adlc.resolvers import Member, ResolverResult
from adlc.resolvers import doc_reference, http_contract, ownership, shared_package

PROJECT_FILE = "adlc-project.yml"


def load_project(project_dir: Path) -> dict:
    data = yaml.safe_load((project_dir / PROJECT_FILE).read_text())["adlc_project"]
    data["_dir"] = project_dir
    return data


def load_members(project: dict, fetch: bool = False) -> list[Member]:
    members = []
    for m in project["members"]:
        if "path" in m:
            path = (project["_dir"] / m["path"]).resolve()
        elif fetch and "url" in m:
            path = _fetch_member(project["_dir"], m)
        else:
            raise SystemExit(f"member {m['repo']}: needs `path` (or `url` with --fetch)")
        gp = path / "graphify-out" / "graph.json"
        if not gp.exists():
            raise SystemExit(f"member {m['repo']}: {gp} missing — run `adlc baseline` there first")
        stamp = path / "graphify-out" / "adlc-stamp.json"
        sha = json.loads(stamp.read_text())["commit_sha"] if stamp.exists() else "unknown"
        members.append(Member(m["repo"], path, sha, gp))
    return members


def _fetch_member(project_dir: Path, m: dict) -> Path:
    import subprocess
    dest = project_dir / ".adlc" / "members" / m["repo"]
    if not dest.exists():
        subprocess.run(["git", "clone", "--depth", "1", "--branch", m.get("ref", "main"), m["url"], str(dest)], check=True)
    else:
        subprocess.run(["git", "-C", str(dest), "pull", "-q"], check=True)
    return dest


def namespaced(member: Member) -> nx.DiGraph:
    data = json.loads(member.graph_path.read_text())
    G = nx.DiGraph()
    for n in data.get("nodes", []):
        nid = f"{member.name}::{n['id']}"
        attrs = {k: v for k, v in n.items() if k != "id"}
        attrs["repo"] = member.name
        attrs["orig_id"] = n["id"]
        G.add_node(nid, **attrs)
    for e in data.get("links", []):
        G.add_edge(f"{member.name}::{e['source']}", f"{member.name}::{e['target']}",
                   **{k: v for k, v in e.items() if k not in ("source", "target")})
    return G


def merge(members: list[Member]) -> nx.DiGraph:
    G = nx.DiGraph()
    for m in members:
        G = nx.compose(G, namespaced(m))
    return G


def apply(G: nx.DiGraph, res: ResolverResult) -> None:
    for nid, attrs in res.nodes.items():
        if nid not in G:
            G.add_node(nid, **attrs)
    for s, t, meta in res.edges:
        if s in G and t in G:
            G.add_edge(s, t, **meta)


def cluster(G: nx.DiGraph) -> dict[str, int]:
    U = nx.Graph(G)
    try:
        from graphify.cluster import _partition
        return _partition(U)
    except Exception:  # pragma: no cover - fallback path
        comms = nx.community.louvain_communities(U, seed=7)
        return {n: i for i, c in enumerate(comms) for n in c}


def federate_project(project_dir: Path, fetch: bool = False) -> dict:
    project = load_project(project_dir)
    members = load_members(project, fetch)
    G = merge(members)
    results = [
        ownership.resolve(members, G, project["name"], project.get("teams") or {}),
        http_contract.resolve(members, G, (project.get("contract_hints") or {}).get("openapi")),
        shared_package.resolve(members, G, (project.get("contract_hints") or {}).get("packages")),
        doc_reference.resolve(members, G),
    ]
    for r in results:
        apply(G, r)
    part = cluster(G)
    nx.set_node_attributes(G, part, "community")
    meta = {
        "level": "project", "project": project["name"], "kit": __version__,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "members": {m.name: {"commit_sha": m.sha} for m in members},
        "resolvers": {r.name: {"edges": len(r.edges), "nodes": len(r.nodes), "ambiguous": len(r.ambiguous)} for r in results},
    }
    G.graph["adlc"] = meta
    out = project_dir / "project-graph.json"
    prev = out.read_text() if out.exists() else None
    data = json_graph.node_link_data(G, edges="links")
    out.write_text(json.dumps(data, separators=(",", ":")))
    (project_dir / "PROJECT_REPORT.md").write_text(project_report(G, members, results, meta, prev))
    return meta


def build_org(project_dirs: list[Path], out_dir: Path) -> dict:
    """L2: COARSE. Nodes = projects, repos, teams, services (cross-repo communities),
    contracts, shared packages. Thousands at most."""
    O = nx.DiGraph()
    versions = {}
    for pd in project_dirs:
        data = json.loads((pd / "project-graph.json").read_text())
        G = json_graph.node_link_graph(data, edges="links", directed=True)
        meta = G.graph["adlc"]
        versions[meta["project"]] = meta["generated_at"]
        for nid, a in G.nodes(data=True):
            if a.get("kind") in ("project", "repo", "team", "service_dir", "http_route", "package"):
                O.add_node(nid, **{k: a[k] for k in ("label", "kind", "repo", "provider_repo", "provider_unit", "commit_sha") if k in a})
        for s, t, e in G.edges(data=True):
            if s in O and t in O:
                O.add_edge(s, t, **{k: e[k] for k in ("relation", "resolver", "confidence") if k in e})
        # service (dir or repo) -> contract edges lifted from file-level edges
        def unit_node(unit: str | None, repo: str | None) -> str | None:
            if unit and "/" in unit:
                r, d = unit.split("/", 1)
                cand = f"{r}::dir::{d}"
                if cand not in O:
                    O.add_node(cand, label=unit, kind="service_dir", repo=r)
                return cand
            return f"repo::{repo}" if repo else None
        comm_repos: dict[int, set] = {}
        for s, t, e in G.edges(data=True):
            if e.get("relation") == "consumes" and t in O:
                u = unit_node(e.get("consumer_unit"), G.nodes[s].get("repo"))
                if u:
                    O.add_edge(u, t, relation="consumes", resolver=e.get("resolver"), confidence="INFERRED")
            elif e.get("relation") == "exposes" and t in O:
                u = unit_node(G.nodes[t].get("provider_unit"), G.nodes[s].get("repo"))
                if u:
                    O.add_edge(u, t, relation="exposes", resolver=e.get("resolver"), confidence="INFERRED")
                    O.nodes[t]["provider_unit"] = G.nodes[t].get("provider_unit")
        for nid, a in G.nodes(data=True):
            if a.get("repo") and "community" in a and a.get("kind") not in ("project", "repo", "team"):
                comm_repos.setdefault(a["community"], set()).add(a["repo"])
        for cid, repos in comm_repos.items():
            if len(repos) >= 2:
                sid = f"service::{meta['project']}::c{cid}"
                O.add_node(sid, label=f"{meta['project']} subsystem {cid}", kind="service", repos=sorted(repos))
                for r in repos:
                    O.add_edge(f"repo::{r}", sid, relation="participates_in", confidence="INFERRED", resolver="leiden")
    meta = {"level": "org", "kit": __version__, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "projects": versions, "nodes": O.number_of_nodes(), "edges": O.number_of_edges()}
    O.graph["adlc"] = meta
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "org-graph.json").write_text(json.dumps(json_graph.node_link_data(O, edges="links"), separators=(",", ":")))
    (out_dir / "ORG_REPORT.md").write_text(org_report(O, meta))
    return meta


def stale_federated(repo: Path, level: str, as_json: bool = False) -> int:
    """project: compare each member's stamped sha with its current HEAD (local members).
    org: compare each project's version stamp with the project's current graph."""
    from adlc.gitinfo import commits_between
    rows, worst = [], 0
    if level == "project":
        pdir = _find_project_dir(repo)
        meta = json.loads((pdir / "project-graph.json").read_text())["graph"]["adlc"]
        project = load_project(pdir)
        for m in project["members"]:
            path = (pdir / m["path"]).resolve() if "path" in m else None
            stamped = meta["members"].get(m["repo"], {}).get("commit_sha")
            behind = commits_between(path, stamped) if path and stamped else None
            code = 0 if behind == 0 else (1 if behind is not None and behind <= 10 else 2)
            worst = max(worst, code)
            rows.append({"member": m["repo"], "stamped": stamped, "behind": behind, "exit": code})
    else:
        odir = _find_org_dir(repo)
        meta = json.loads((odir / "org-graph.json").read_text())["graph"]["adlc"]
        for name, ver in meta["projects"].items():
            pg = _find_project_dir(repo, name) / "project-graph.json"
            cur = json.loads(pg.read_text())["graph"]["adlc"]["generated_at"] if pg.exists() else None
            code = 0 if cur == ver else 2
            worst = max(worst, code)
            rows.append({"project": name, "org_has": ver, "project_now": cur, "exit": code})
    if as_json:
        print(json.dumps(rows))
    else:
        for r in rows:
            print(f"[{level}] " + " ".join(f"{k}={v}" for k, v in r.items()))
    return worst


def _find_project_dir(start: Path, name: str | None = None) -> Path:
    for cand in [start, *start.parents]:
        if (cand / PROJECT_FILE).exists():
            return cand
        org = cand / "org"
        if org.exists():
            for p in org.iterdir():
                if (p / PROJECT_FILE).exists() and (name is None or load_project(p)["name"] == name):
                    return p
    raise SystemExit("no adlc-project.yml found")


def _find_org_dir(start: Path) -> Path:
    for cand in [start, *start.parents]:
        for p in (cand / "org-graph.json", cand / ".github-private" / "org-graph.json", cand / "org" / ".github-private" / "org-graph.json"):
            if p.exists():
                return p.parent
    raise SystemExit("no org-graph.json found")


def add_parser(sub) -> None:
    p = sub.add_parser("federate", help="build the L1 project graph (or --level org)")
    p.add_argument("--level", choices=["project", "org"], default="project")
    p.add_argument("--project-dir", default=".", help="dir with adlc-project.yml (project level)")
    p.add_argument("--projects", nargs="*", default=None, help="project dirs (org level; default: ../*/adlc-project.yml)")
    p.add_argument("--out", default=None, help="org output dir (default: ./.github-private or .)")
    p.add_argument("--fetch", action="store_true", help="clone/pull url members")
    p.set_defaults(func=run)


def run(args) -> int:
    if args.level == "project":
        meta = federate_project(Path(args.project_dir).resolve(), fetch=args.fetch)
        res = ", ".join(f"{k}:{v['edges']}e/{v['ambiguous']}a" for k, v in meta["resolvers"].items())
        print(f"project graph for {meta['project']} — members {list(meta['members'])}; resolvers {res}")
        return 0
    here = Path(args.project_dir).resolve()
    dirs = [Path(p).resolve() for p in args.projects] if args.projects else sorted(
        p for p in (here if (here / PROJECT_FILE).exists() is False else here.parent).iterdir() if (p / PROJECT_FILE).exists())
    out = Path(args.out).resolve() if args.out else here
    meta = build_org(dirs, out)
    print(f"org graph: {meta['nodes']} nodes, {meta['edges']} edges from projects {list(meta['projects'])} → {out}")
    return 0
