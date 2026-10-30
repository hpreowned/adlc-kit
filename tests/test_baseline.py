import json

from adlc import baseline
from adlc.gitinfo import head_sha
from adlc.stale import STAMP_NAME, check


def _graph(repo, nodes):
    out = repo / "graphify-out"
    out.mkdir(exist_ok=True)
    (out / "graph.json").write_text(json.dumps({"directed": False, "graph": {}, "nodes": nodes, "links": []}))


def test_stamp_writes_sidecar_and_graph_meta(repo):
    _graph(repo, [{"id": "a", "file_type": "code"}])
    info = baseline.stamp(repo, "graphify-out/graph.json", {"mode": "test"})
    assert info["commit_sha"] == head_sha(repo) and info["nodes"] == 1
    side = json.loads((repo / "graphify-out" / STAMP_NAME).read_text())
    assert side["commit_sha"] == head_sha(repo)
    g = json.loads((repo / "graphify-out/graph.json").read_text())
    assert g["graph"]["adlc"]["mode"] == "test"
    assert check(repo, "graphify-out/graph.json").exit_code == 0


def test_docs_only_repo_with_semantic_graph_is_stamp_only(repo, capsys):
    _graph(repo, [{"id": "c1", "file_type": "concept"}, {"id": "d1", "file_type": "document"}])
    info = baseline.build(repo, viz=False)
    assert info["mode"] == "stamp-only" and info["nodes"] == 2
    assert "stamping only" in capsys.readouterr().out


def test_has_semantic_nodes(repo):
    _graph(repo, [{"id": "x", "file_type": "code"}])
    assert not baseline.has_semantic_nodes(repo / "graphify-out/graph.json")
    _graph(repo, [{"id": "x", "file_type": "rationale"}])
    assert baseline.has_semantic_nodes(repo / "graphify-out/graph.json")
