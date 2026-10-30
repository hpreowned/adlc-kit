"""shared-package: a member that publishes a package (pyproject / package.json / csproj /
pom) ↔ members that import it."""
from __future__ import annotations

import re

import networkx as nx

from adlc.resolvers import Member, ResolverResult, file_node, iter_source_files

IMPORT_PATTERNS = [
    re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][\w.]*)", re.M),            # python
    re.compile(r"from\s+['\"](@?[A-Za-z0-9_./-]+)['\"]"),                     # ts/js
    re.compile(r"^\s*using\s+([A-Z][\w.]*)\s*;", re.M),                       # c#
    re.compile(r"^\s*import\s+([a-z][\w.]*)\.", re.M),                        # java (group prefix)
]


def published_packages(m: Member, extra: list[str]) -> list[str]:
    names: list[str] = list(extra)
    for f in iter_source_files(m, (".toml", ".json", ".csproj", ".xml")):
        text = f.read_text(errors="ignore")
        if f.name == "pyproject.toml":
            mm = re.search(r"^\s*name\s*=\s*['\"]([^'\"]+)['\"]", text, re.M)
            if mm:
                names.append(mm.group(1))
        elif f.name == "package.json" and '"private": true' not in text:
            mm = re.search(r'"name"\s*:\s*"([^"]+)"', text)
            if mm:
                names.append(mm.group(1))
        elif f.suffix == ".csproj":
            mm = re.search(r"<(?:PackageId|AssemblyName)>([^<]+)<", text)
            if mm and "<IsPackable>true" in text.replace(" ", ""):
                names.append(mm.group(1))
        elif f.name == "pom.xml":
            mm = re.search(r"<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>", text)
            if mm:
                names.append(mm.group(1))
    return sorted(set(n for n in names if n))


def resolve(members: list[Member], G: nx.Graph, extra_packages: list[str] | None = None) -> ResolverResult:
    r = ResolverResult("shared-package")
    pubs = {m.name: published_packages(m, extra_packages or []) for m in members}
    for m in members:
        for f in iter_source_files(m, (".py", ".ts", ".tsx", ".cs", ".java")):
            text = f.read_text(errors="ignore")
            imported = {i for pat in IMPORT_PATTERNS for i in pat.findall(text)}
            for other, names in pubs.items():
                if other == m.name:
                    continue
                for name in names:
                    if any(i == name or i.startswith(name + ".") or i.startswith(name + "/") for i in imported):
                        pkg = r.add_node(f"package::{name}", label=name, kind="package", file_type="contract", provider_repo=other)
                        src = file_node(G, m.name, str(f.relative_to(m.path)))
                        if src:
                            r.add_edge(src, pkg, "imports", at=str(f.relative_to(m.path)))
    return r
