"""doc-reference: ticket ids, ADR numbers, postmortem slugs and *file paths* cited across
repos — the cheapest, most reliable join key. Emits `ref::<id>` nodes and `cites` edges,
plus direct doc→code edges when a document names a file that exists in another member."""
from __future__ import annotations

import re

import networkx as nx

from adlc.resolvers import Member, ResolverResult, file_node, iter_source_files

TICKET = re.compile(r"\b([A-Z]{2,6}-\d{2,6})\b")
ADR = re.compile(r"\b(?:ADR[- ]?0*(\d{1,4})|adr/0*(\d{1,4})-)", re.I)
POSTMORTEM = re.compile(r"\b(\d{4}-\d{2}-\d{2}-[a-z][a-z0-9-]+)\b")
DOC_EXTS = (".md", ".csv", ".txt", ".yml", ".yaml", ".json")
CODE_EXTS = (".py", ".ts", ".tsx", ".java", ".cs", ".sql", ".toml", ".xml", ".csproj")
STOP_TICKET_PREFIXES = {"UTF", "ISO", "RFC", "SHA", "HTTP", "TLS", "AES", "CVE", "SOC", "ID", "KB", "ADR", "PM", "NET"}


def _repo_files(m: Member) -> set[str]:
    return {str(p.relative_to(m.path)) for p in iter_source_files(m, CODE_EXTS + DOC_EXTS)}


def _ids(text: str) -> dict[str, set[str]]:
    out = {"ticket": set(), "adr": set(), "postmortem": set()}
    for t in TICKET.findall(text):
        if t.split("-")[0] not in STOP_TICKET_PREFIXES:
            out["ticket"].add(t)
    for a, b in ADR.findall(text):
        out["adr"].add(f"ADR-{int(a or b):04d}")
    out["postmortem"].update(POSTMORTEM.findall(text))
    return out


def resolve(members: list[Member], G: nx.Graph) -> ResolverResult:
    r = ResolverResult("doc-reference")
    files_by_repo = {m.name: _repo_files(m) for m in members}
    all_paths = {(m.name, f) for m in members for f in files_by_repo[m.name] if "/" in f}
    for m in members:
        for p in iter_source_files(m, CODE_EXTS + DOC_EXTS):
            try:
                text = p.read_text(errors="ignore")
            except OSError:
                continue
            rel = str(p.relative_to(m.path))
            src = file_node(G, m.name, rel) or r.add_node(f"{m.name}::file::{rel}", label=rel, repo=m.name,
                                                             source_file=rel, file_type="document", kind="file")
            for kind, ids in _ids(text).items():
                for i in ids:
                    ref = r.add_node(f"ref::{i}", label=i, kind=kind, file_type="reference")
                    r.add_edge(src, ref, "cites", at=rel)
            if p.suffix in DOC_EXTS:
                for repo, path in all_paths:
                    if repo == m.name or path not in text:
                        continue
                    hit = file_node(G, repo, path)
                    if hit is None and (next(mm.path for mm in members if mm.name == repo) / path).exists():
                        hit = r.add_node(f"{repo}::file::{path}", label=path.split("/")[-1], repo=repo, source_file=path,
                                         file_type="code", kind="file")
                    if hit:
                        r.add_edge(src, hit, "references_file", at=rel, path=path)
                    else:
                        r.ambiguous.append({"resolver": "doc-reference", "repo": m.name, "file": rel,
                                            "issue": f"cites {repo}:{path} but no graph node for it"})
    return r
