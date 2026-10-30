"""ownership: CODEOWNERS → team nodes; team → repo / service dir; repo → project."""
from __future__ import annotations

import networkx as nx

from adlc.resolvers import Member, ResolverResult


def parse_codeowners(text: str) -> list[tuple[str, list[str]]]:
    rules = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        rules.append((parts[0], parts[1:]))
    return rules


def resolve(members: list[Member], G: nx.Graph, project: str, team_map: dict[str, str]) -> ResolverResult:
    r = ResolverResult("ownership")
    pnode = r.add_node(f"project::{project}", label=project, kind="project", file_type="org")
    for m in members:
        rnode = r.add_node(f"repo::{m.name}", label=m.name, kind="repo", file_type="org", commit_sha=m.sha)
        r.add_edge(rnode, pnode, "member_of")
        co = next((p for p in (m.path / "CODEOWNERS", m.path / ".github" / "CODEOWNERS") if p.exists()), None)
        if not co:
            r.ambiguous.append({"resolver": "ownership", "repo": m.name, "issue": "no CODEOWNERS"})
            continue
        for pattern, teams in parse_codeowners(co.read_text()):
            for t in teams:
                tnode = r.add_node(f"team::{t}", label=t, kind="team", file_type="org")
                if pattern == "*":
                    r.add_edge(tnode, rnode, "owns", pattern=pattern)
                else:
                    svc = pattern.strip("/").split("/")[0]
                    snode = r.add_node(f"{m.name}::dir::{svc}", label=f"{m.name}/{svc}", kind="service_dir",
                                       repo=m.name, file_type="org")
                    r.add_edge(snode, rnode, "part_of")
                    r.add_edge(tnode, snode, "owns", pattern=pattern)
                proj = team_map.get(t)
                if proj:
                    r.add_edge(tnode, f"project::{proj}", "works_on")
    return r
