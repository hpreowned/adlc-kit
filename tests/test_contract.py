import pytest

from adlc import contract as C
from tests.conftest import AGENTS


def test_parse_ok():
    c = C.parse(AGENTS)
    assert c.schema == 1 and c.context == ["graphify", "serena"]
    assert c.artifact == "graphify-out/graph.json" and c.sensitive == ["migrations/"]


def test_missing_block():
    with pytest.raises(C.ContractError, match="no fenced"):
        C.parse("# AGENTS.md\nnothing here\n")


def test_missing_key():
    bad = AGENTS.replace("  kit: 0.1.0\n", "")
    with pytest.raises(C.ContractError, match="missing keys: kit"):
        C.parse(bad)


def test_bad_context():
    with pytest.raises(C.ContractError, match="context"):
        C.parse(AGENTS.replace("[graphify, serena]", "[sourcegraph]"))


def test_replace_block_roundtrip_keeps_prose():
    c = C.parse(AGENTS)
    c.kit = "0.2.0"
    out = C.replace_block(AGENTS, c)
    assert "Build: `make test`" in out
    assert C.parse(out).kit == "0.2.0"
    assert out.count("```yaml") == 1


def test_referenced_paths(tmp_path):
    (tmp_path / "docs").mkdir()
    text = AGENTS + "\nSee `docs/adr/0001.md`, `adr/NNNN-slug.md`, `other-repo:x.md`, `Makefile`, `pom.xml`, e.g. `vs`.\n"
    got = C.referenced_paths(text, tmp_path)
    assert "docs/adr/0001.md" in got and "pom.xml" in got
    assert not any("NNNN" in g or "other-repo" in g for g in got)
    assert "vs" not in got
