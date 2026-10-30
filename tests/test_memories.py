from adlc.memories import contract_memory, graph_memory, write_memories


def test_contract_memory_sections(repo):
    (repo / "AGENTS.md").write_text((repo / "AGENTS.md").read_text().replace("Build: `make test`.", "## Build, test, run, lint\n- Test: `make test`\n\n## Do not touch\n- `migrations/`\n"))
    m = contract_memory(repo)
    assert "## Build, test, run, lint" in m and "`make test`" in m and "## Do not touch" in m
    assert "artifact: `graphify-out/graph.json`" in m


def test_graph_memory_from_report(repo):
    out = repo / "graphify-out"
    out.mkdir()
    (out / "GRAPH_REPORT.md").write_text("# Graph Report\n\n## Summary\n- 10 nodes\n\n## God Nodes (most connected - your core abstractions)\n1. `Foo` - 9 edges\n\n## Other\nx\n")
    g = graph_memory(repo, "graphify-out/graph.json")
    assert "10 nodes" in g and "`Foo`" in g
    paths = write_memories(repo, "graphify-out/graph.json")
    assert [p.name for p in paths] == ["adlc_contract.md", "adlc_graph_summary.md"]
