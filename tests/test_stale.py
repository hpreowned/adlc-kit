import json

from adlc import stale
from adlc.gitinfo import head_sha
from tests.conftest import commit


def _stamp(repo, sha):
    out = repo / "graphify-out"
    out.mkdir(exist_ok=True)
    (out / "graph.json").write_text(json.dumps({"directed": True, "graph": {}, "nodes": [], "links": []}))
    (out / stale.STAMP_NAME).write_text(json.dumps({"commit_sha": sha, "generated_at": "2026-10-30T00:00:00Z"}))


def test_missing_artifact_is_exit_2(repo):
    s = stale.check(repo, "graphify-out/graph.json")
    assert s.exit_code == 2 and not s.exists


def test_fresh_is_exit_0(repo):
    _stamp(repo, head_sha(repo))
    s = stale.check(repo, "graphify-out/graph.json")
    assert s.exit_code == 0 and s.behind == 0
    assert "FRESH" in s.line()


def test_usable_within_threshold_is_exit_1(repo):
    _stamp(repo, head_sha(repo))
    commit(repo, "a.txt")
    commit(repo, "b.txt")
    s = stale.check(repo, "graphify-out/graph.json", threshold=10)
    assert s.exit_code == 1 and s.behind == 2


def test_beyond_threshold_is_exit_2(repo):
    _stamp(repo, head_sha(repo))
    for i in range(3):
        commit(repo, f"f{i}.txt")
    s = stale.check(repo, "graphify-out/graph.json", threshold=2)
    assert s.exit_code == 2 and s.behind == 3


def test_unknown_sha_is_exit_2(repo):
    _stamp(repo, "0" * 40)
    s = stale.check(repo, "graphify-out/graph.json")
    assert s.exit_code == 2 and s.behind is None


def test_stamp_fallback_inside_graph_json(repo):
    out = repo / "graphify-out"
    out.mkdir()
    (out / "graph.json").write_text(json.dumps({"graph": {"adlc": {"commit_sha": head_sha(repo)}}, "nodes": [], "links": []}))
    s = stale.check(repo, "graphify-out/graph.json")
    assert s.exit_code == 0
