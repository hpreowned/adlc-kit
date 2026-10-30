from pathlib import Path

from harness.events import find_events_file, parse_events, parse_file

FIX = Path(__file__).parent / "fixtures" / "events_smoke.jsonl"


def test_parses_shutdown_totals():
    m = parse_file(FIX)
    assert m.shutdown_seen
    assert m.input_tokens > 0 and m.output_tokens > 0
    assert m.premium_requests is not None
    assert m.api_duration_ms > 0
    assert m.copilot_version.startswith("1.")


def test_turns_tools_and_skills():
    m = parse_file(FIX)
    assert m.turns == 2
    assert sum(m.tool_calls.values()) == 1
    assert m.skills_invoked == ["alpha-skill"]
    assert m.models  # at least one model observed


def test_usage_record_cross_check():
    m = parse_file(FIX)
    assert m.model_calls == 2
    assert m.premium_cost_sum == 2.0  # two calls at multiplier 1.0 each


def test_unknown_types_are_counted_not_fatal():
    m = parse_events(['{"type":"future.thing","data":{}}', "not json", ""])
    assert m.unknown_event_types == {"future.thing": 1}
    assert m.event_count == 1
    assert not m.shutdown_seen


def test_find_events_file(tmp_path):
    assert find_events_file(tmp_path) is None
    d = tmp_path / "session-state" / "abc"
    d.mkdir(parents=True)
    (d / "events.jsonl").write_text("{}\n")
    assert find_events_file(tmp_path) == d / "events.jsonl"
