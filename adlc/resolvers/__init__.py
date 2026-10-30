"""Cross-repo edge resolvers for `adlc federate`. Each resolver is a pure function
`(members, G) -> ResolverResult` where `members` is the list of loaded member repos and
`G` the merged, namespaced graph. Every emitted edge is tagged confidence=INFERRED and
`resolver=<name>`; unresolved items become AMBIGUOUS entries for the report."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import networkx as nx


@dataclass
class Member:
    name: str
    path: Path
    sha: str
    graph_path: Path


@dataclass
class ResolverResult:
    name: str
    edges: list[tuple[str, str, dict]] = field(default_factory=list)
    nodes: dict[str, dict] = field(default_factory=dict)
    ambiguous: list[dict] = field(default_factory=list)

    def add_edge(self, src: str, dst: str, relation: str, **meta) -> None:
        self.edges.append((src, dst, {"relation": relation, "confidence": "INFERRED", "resolver": self.name, **meta}))

    def add_node(self, nid: str, **attrs) -> str:
        self.nodes.setdefault(nid, attrs)
        return nid


def file_node(G: nx.Graph, repo: str, rel_path: str) -> str | None:
    """The namespaced node that represents a source file in a member graph: prefer
    graphify's file-level node (label == basename), then a document node, then the
    first symbol defined in that file."""
    base = rel_path.rsplit("/", 1)[-1]
    first = doc = None
    for nid, data in G.nodes(data=True):
        if data.get("repo") != repo or data.get("source_file") != rel_path:
            continue
        if data.get("label") == base:
            return nid
        if data.get("file_type") == "document" and doc is None:
            doc = nid
        first = first or nid
    return doc or first


def iter_source_files(member: Member, exts: tuple[str, ...]) -> list[Path]:
    skip = {".git", "node_modules", ".venv", "target", "bin", "obj", "graphify-out", "dist", "__pycache__", ".serena"}
    out = []
    for p in member.path.rglob("*"):
        if any(part in skip for part in p.parts):
            continue
        if p.is_file() and p.suffix in exts:
            out.append(p)
    return out
