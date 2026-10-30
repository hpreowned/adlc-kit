"""http-contract: provider route declarations (FastAPI / Spring / .NET minimal API) ↔
consumer HTTP calls (httpx/requests, fetch/axios, HttpClient/RestTemplate). Match on
METHOD + normalised path template. The unit of "who talks to whom" is a *service*: a
repo, or a service directory inside a polyglot repo. Unmatched consumer calls → AMBIGUOUS.
Test files are neither providers nor consumers."""
from __future__ import annotations

import re
from pathlib import Path

import networkx as nx

from adlc.render import detect_services
from adlc.resolvers import Member, ResolverResult, file_node, iter_source_files

PROVIDER_PATTERNS = [
    (re.compile(r"@(?:\w+)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]*)['\"]"), "python"),
    (re.compile(r"@(Get|Post|Put|Patch|Delete)Mapping(?:\(\s*(?:value\s*=\s*|path\s*=\s*)?['\"]([^'\"]*)['\"])?"), "java"),
    (re.compile(r"\.Map(Get|Post|Put|Patch|Delete)\(\s*['\"]([^'\"]*)['\"]"), "csharp"),
]
PREFIX_PATTERNS = [
    re.compile(r"APIRouter\([^)]*prefix\s*=\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"include_router\([^)]*prefix\s*=\s*['\"]([^'\"]+)['\"]"),
    re.compile(r"MapGroup\(\s*['\"]([^'\"]+)['\"]"),
]
CLASS_PREFIX = re.compile(r"@RequestMapping\(\s*(?:value\s*=\s*|path\s*=\s*)?['\"]([^'\"]+)['\"]")
CONSUMER_PATH = re.compile(r"['\"`](/(?:api|v\d+)/[A-Za-z0-9_./{}:$\-]*)['\"`]")
CONSUMER_METHOD = re.compile(r"\.(get|post|put|patch|delete)\s*\(", re.I)
CODE_EXTS = (".py", ".ts", ".tsx", ".java", ".cs")
TEST_MARKERS = ("/test/", "/tests/", ".test.", ".spec.", "Tests/", "_test.", "test_", "conftest")


def normalise(path: str) -> str:
    p = re.sub(r"\$\{[^}]*\}", ":p", path)
    p = re.sub(r"\{[^}]*\}", ":p", p)
    p = re.sub(r":[A-Za-z_]+", ":p", p)
    return "/" + p.strip("/").lower()


def _is_test(rel: str) -> bool:
    return any(t in rel for t in TEST_MARKERS)


def unit_of(m: Member, rel: str, services: dict) -> str:
    top = rel.split("/")[0]
    return f"{m.name}/{top}" if top in services else m.name


def _join(prefix: str, path: str) -> str:
    if not prefix:
        return path or "/"
    if path.startswith(prefix):
        return path
    return prefix.rstrip("/") + ("/" + path.lstrip("/") if path else "")


def _handler_after(text: str, pos: int) -> str | None:
    m = re.search(r"\b(?:def|async def)\s+(\w+)|\b(?:public|private|internal)?\s*(?:static\s+)?[\w<>\[\]]+\s+(\w+)\s*\(", text[pos:pos + 600])
    return (m.group(1) or m.group(2)) if m else None


INCLUDE_ROUTER = re.compile(r"include_router\(\s*(\w+)\.router[^)]*?prefix\s*=\s*['\"]([^'\"]+)['\"]")
ROUTER_DECL = re.compile(r"\b(\w+)\s*=\s*APIRouter\((?:[^)]*prefix\s*=\s*['\"]([^'\"]*)['\"])?")
MAPGROUP_DECL = re.compile(r"\b(?:var\s+)?(\w+)\s*=\s*(\w+)\.MapGroup\(\s*['\"]([^'\"]*)['\"]")
NET_ROUTE = re.compile(r"\b(\w+)\.Map(Get|Post|Put|Patch|Delete)\(\s*['\"]([^'\"]*)['\"]")


def _net_group_prefixes(texts: dict[Path, str], unit_files: list[Path]) -> dict[str, str]:
    """Resolve `var x = parent.MapGroup("/p")` chains across the unit's files."""
    decls = {}
    for f in unit_files:
        for var, parent, path in MAPGROUP_DECL.findall(texts[f]):
            decls[var] = (parent, path)
    out: dict[str, str] = {}

    def prefix(var: str, depth: int = 0) -> str:
        if var not in decls or depth > 8:
            return ""
        parent, path = decls[var]
        return _join(prefix(parent, depth + 1), path).rstrip("/")
    for var in decls:
        out[var] = prefix(var)
    return out


def provider_routes(m: Member) -> list[dict]:
    services = detect_services(m.path)
    files = [f for f in iter_source_files(m, CODE_EXTS) if not _is_test(str(f.relative_to(m.path)))]
    texts = {f: f.read_text(errors="ignore") for f in files}
    by_unit: dict[str, list[Path]] = {}
    for f in files:
        by_unit.setdefault(unit_of(m, str(f.relative_to(m.path)), services), []).append(f)
    include_prefix: dict[str, dict[str, str]] = {}   # unit -> module stem -> prefix
    net_groups: dict[str, dict[str, str]] = {}
    for u, fl in by_unit.items():
        include_prefix[u] = {mod: pre for f in fl for mod, pre in INCLUDE_ROUTER.findall(texts[f])}
        net_groups[u] = _net_group_prefixes(texts, fl)
    routes = []
    for f, text in texts.items():
        rel = str(f.relative_to(m.path))
        u = unit_of(m, rel, services)
        cls = CLASS_PREFIX.search(text)
        file_prefix = cls.group(1) if cls else ""
        rd = ROUTER_DECL.search(text)
        if rd:
            file_prefix = _join(include_prefix[u].get(f.stem, ""), rd.group(2) or "")
        for mm in NET_ROUTE.finditer(text):
            var, method, path = mm.group(1), mm.group(2).lower(), mm.group(3)
            full = _join(net_groups[u].get(var, ""), path)
            routes.append(_route(m, u, rel, text, mm, method, full, "csharp"))
        for pat, lang in PROVIDER_PATTERNS:
            if lang == "csharp":
                continue
            for mm in pat.finditer(text):
                method, path = mm.group(1).lower(), mm.group(2) or ""
                routes.append(_route(m, u, rel, text, mm, method, _join(file_prefix, path), lang))
    return routes


def _route(m, u, rel, text, mm, method, full, lang) -> dict:
    full = full if full.startswith("/") else "/" + full
    return {"repo": m.name, "unit": u, "file": rel, "line": text.count("\n", 0, mm.start()) + 1, "method": method,
            "path": full, "norm": normalise(full), "lang": lang, "handler": _handler_after(text, mm.end())}


def consumer_calls(m: Member) -> list[dict]:
    services = detect_services(m.path)
    calls = []
    for f in iter_source_files(m, CODE_EXTS):
        rel = str(f.relative_to(m.path))
        if _is_test(rel):
            continue
        text = f.read_text(errors="ignore")
        for mm in CONSUMER_PATH.finditer(text):
            path = mm.group(1)
            window = text[max(0, mm.start() - 160): mm.start()]
            meth = CONSUMER_METHOD.findall(window)
            calls.append({"repo": m.name, "unit": unit_of(m, rel, services), "file": rel,
                          "line": text.count("\n", 0, mm.start()) + 1, "path": path, "norm": normalise(path),
                          "method": meth[-1].lower() if meth else None})
    return calls


def resolve(members: list[Member], G: nx.Graph, openapi_files: list[str] | None = None) -> ResolverResult:
    r = ResolverResult("http-contract")
    routes = [rt for m in members for rt in provider_routes(m)]
    by_norm: dict[str, list[dict]] = {}
    for rt in routes:
        by_norm.setdefault(rt["norm"], []).append(rt)
    for rt in routes:
        rid = r.add_node(f"contract::{rt['method'].upper()} {rt['norm']}", label=f"{rt['method'].upper()} {rt['path']}",
                         kind="http_route", file_type="contract", provider_repo=rt["repo"], provider_unit=rt["unit"])
        handler = file_node(G, rt["repo"], rt["file"])
        if handler:
            r.add_edge(handler, rid, "exposes", at=f"{rt['file']}:{rt['line']}", handler=rt["handler"])
    for m in members:
        for call in consumer_calls(m):
            all_cands = by_norm.get(call["norm"], [])
            if call["method"]:
                exact = [rt for rt in all_cands if rt["method"] == call["method"]]
                all_cands = exact or all_cands
            cross = [rt for rt in all_cands if rt["unit"] != call["unit"]]
            if not all_cands:
                r.ambiguous.append({"resolver": "http-contract", "repo": m.name, "file": call["file"], "line": call["line"],
                                    "issue": f"calls {call['method'] or '?'} {call['path']} — no provider route found in any member"})
                continue
            if not cross:
                continue  # a service declaring and calling its own route (self-test, client stub) is not a contract
            src = file_node(G, m.name, call["file"]) or r.add_node(f"{m.name}::file::{call['file']}", label=call["file"],
                                                                      repo=m.name, source_file=call["file"], file_type="code")
            for rt in cross:
                r.add_edge(src, f"contract::{rt['method'].upper()} {rt['norm']}", "consumes",
                           at=f"{call['file']}:{call['line']}", method=call["method"] or rt["method"], consumer_unit=call["unit"])
    return r
