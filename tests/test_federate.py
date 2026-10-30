"""Federation tests. The Kestrel repos are the fixtures when present (pilot machine);
synthetic graphs cover the pure functions everywhere."""
import json
from pathlib import Path

import networkx as nx
import pytest
from networkx.readwrite import json_graph

from adlc import federate, query as Q
from adlc.resolvers import Member, http_contract, doc_reference, ownership, shared_package

PILOT = Path(__file__).resolve().parents[2]
PROJECT = PILOT / "org" / "kestrel-project"
HAVE_KESTREL = (PROJECT / "adlc-project.yml").exists() and (PILOT / "repos" / "kestrel-web" / "graphify-out" / "graph.json").exists()
kestrel = pytest.mark.skipif(not HAVE_KESTREL, reason="Kestrel fixtures not present")


def test_normalise_route_templates():
    n = http_contract.normalise
    assert n("/v2/shipments/{id}") == n("/v2/shipments/:id") == n("/v2/shipments/${shipmentId}") == "/v2/shipments/:p"
    assert n("api/quote/") == "/api/quote"


def test_http_contract_synthetic(tmp_path):
    prov = tmp_path / "svc"; (prov / "app").mkdir(parents=True)
    (prov / "app" / "routes.py").write_text('router = APIRouter(prefix="/v9")\n@router.get("/things/{tid}")\ndef get_thing(tid): ...\n')
    (prov / "pyproject.toml").write_text("[project]\nname='svc'\n")
    cons = tmp_path / "web"; (cons / "src").mkdir(parents=True)
    (cons / "src" / "client.ts").write_text('export const routes = { thing: "/v9/things/:id" };\nfetch(routes.thing);\n')
    (cons / "package.json").write_text('{"name":"web","private":true}')
    members = [Member("svc", prov, "a" * 40, prov / "x.json"), Member("web", cons, "b" * 40, cons / "x.json")]
    G = nx.DiGraph()
    G.add_node("svc::routes", repo="svc", source_file="app/routes.py", label="routes.py")
    G.add_node("web::client", repo="web", source_file="src/client.ts", label="client.ts")
    r = http_contract.resolve(members, G)
    rels = {(s, t, e["relation"]) for s, t, e in r.edges}
    assert ("svc::routes", "contract::GET /v9/things/:p", "exposes") in rels
    assert ("web::client", "contract::GET /v9/things/:p", "consumes") in rels
    assert r.ambiguous == []


def test_ownership_parses_codeowners(tmp_path):
    repo = tmp_path / "r"; repo.mkdir()
    (repo / "CODEOWNERS").write_text("* @org/platform\n/booking/ @org/booking\n")
    m = Member("r", repo, "c" * 40, repo / "x.json")
    r = ownership.resolve([m], nx.DiGraph(), "proj", {"@org/booking": "proj"})
    rels = {(s, t, e["relation"]) for s, t, e in r.edges}
    assert ("team::@org/platform", "repo::r", "owns") in rels
    assert ("team::@org/booking", "r::dir::booking", "owns") in rels and ("team::@org/booking", "project::proj", "works_on") in rels


def test_doc_reference_ids():
    ids = doc_reference._ids("See PRC-233 and ADR-0007 (adr/0007-rate-limit) after 2026-06-14-double-booking; UTF-8 ok")
    assert ids["ticket"] == {"PRC-233"} and ids["adr"] == {"ADR-0007"} and "2026-06-14-double-booking" in ids["postmortem"]


def test_bfs_free_contract_hops_and_ranking():
    G = nx.DiGraph()
    G.add_node("c1", label="POST /v2/x", kind="http_route"); G.add_node("gw", label="gw.py", repo="s", source_file="gw.py")
    G.add_node("c2", label="POST /api/x", kind="http_route"); G.add_node("web", label="client.ts", repo="w", source_file="client.ts")
    G.add_node("other", label="other.py", repo="s", source_file="other.py"); G.add_node("t", label="x.test.ts", repo="w", source_file="x.test.ts")
    G.add_edge("gw", "c1", relation="consumes"); G.add_edge("gw", "c2", relation="exposes"); G.add_edge("web", "c2", relation="consumes")
    G.add_edge("gw", "other", relation="calls"); G.add_edge("t", "web", relation="imports")
    nodes, _ = Q.bfs(G, ["c1"], 1)
    assert "web" in nodes
    ordered = Q.order_nodes(G, nodes, ["c1"], include_tests=False)
    assert ordered[:4] == ["c1", "gw", "c2", "web"] and "t" not in ordered
    assert Q.seeds_for(G, "what consumes /v2/x") == ["c1"]


@kestrel
def test_kestrel_project_graph_has_contract_chain():
    meta = federate.federate_project(PROJECT)
    assert set(meta["members"]) == {"kestrel-services", "kestrel-web", "kestrel-ops"}
    assert meta["resolvers"]["http-contract"]["ambiguous"] == 0
    G = Q.load(PROJECT / "project-graph.json")
    seeds = Q.seeds_for(G, "what consumes /v2/shipments")
    nodes, _ = Q.bfs(G, seeds, 2)
    ordered = Q.order_nodes(G, nodes, seeds, False)
    top = [G.nodes[n].get("source_file", "") for n in ordered[:12]]
    assert any("gateway/gateway/clients/booking.py" in t for t in top), top
    assert any(t == "src/api/client.ts" for t in top), top
    # the rounding ticket links pricing (C#) and web (TS) via doc-reference
    ticket = [n for n in G.nodes if G.nodes[n].get("label", "").startswith("PRC-233") or n.endswith("tickets/PRC-233.md")]
    assert ticket
    targets = {G.nodes[t].get("source_file") for s in ticket for _, t, e in G.out_edges(s, data=True) if e.get("relation") == "references_file"}
    assert any(t and t.endswith("QuoteCalculator.cs") for t in targets) and "src/lib/money.ts" in targets, targets


@kestrel
def test_kestrel_org_graph_ownership(tmp_path):
    meta = federate.build_org([PROJECT], tmp_path)
    O = json_graph.node_link_graph(json.loads((tmp_path / "org-graph.json").read_text()), edges="links", directed=True)
    kinds = {a.get("kind") for _, a in O.nodes(data=True)}
    assert {"team", "project", "repo", "http_route"} <= kinds
    assert O.has_edge("team::@kestrel/booking-team", "kestrel-services::dir::booking")
    assert O.has_edge("team::@kestrel/web-team", "repo::kestrel-web")
    assert meta["nodes"] < 5000  # L2 is coarse by design
