import json
import os
from datetime import datetime, timedelta, timezone


def test_trace_logging_writes_ordered_flow_events(tmp_path, monkeypatch):
    import core.trace_logging as tl

    monkeypatch.setattr(tl, "TRACE_LOGGING_ENABLED", True)
    monkeypatch.setattr(tl, "TRACE_LOG_DIR", tmp_path)
    monkeypatch.setattr(tl, "TRACE_LOG_RETENTION_DAYS", 7)

    tl.initialize()
    tl.set_session_id("session-1")
    turn_id = tl.start_turn("hello", mode="interactive")
    request_id = tl.start_llm_request(
        prompt="hello",
        context="ctx",
        full_prompt="ctx\n\nhello",
        attempt=1,
        provider="openai",
        model="openai:gpt-4o",
    )
    tool_call_id = tl.log_tool_call_start(tool_name="find_files", args=("notes",), kwargs={})
    tl.log_tool_call_end(
        tool_call_id=tool_call_id,
        tool_name="find_files",
        status="ok",
        result="/home/jadon/notes.txt",
        elapsed_ms=12,
    )
    tl.log_llm_response(response="Found it.", attempt=1, latency_ms=55)
    tl.end_turn(status="ok", assistant_response="Found it.", latency_ms=88)

    [log_file] = list(tmp_path.glob("trace-*.jsonl"))
    lines = log_file.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]

    assert [e["event"] for e in events] == [
        "turn_start",
        "llm_request",
        "tool_call_start",
        "tool_call_end",
        "llm_response",
        "turn_end",
    ]
    assert all(e["session_id"] == "session-1" for e in events)
    assert all(e["turn_id"] == turn_id for e in events)
    assert events[1]["request_id"] == request_id
    assert events[2]["request_id"] == request_id
    assert events[3]["request_id"] == request_id


def test_trace_logging_cleanup_removes_files_older_than_retention(tmp_path, monkeypatch):
    import core.trace_logging as tl

    monkeypatch.setattr(tl, "TRACE_LOGGING_ENABLED", True)
    monkeypatch.setattr(tl, "TRACE_LOG_DIR", tmp_path)
    monkeypatch.setattr(tl, "TRACE_LOG_RETENTION_DAYS", 7)

    old_file = tmp_path / "trace-old.jsonl"
    new_file = tmp_path / "trace-new.jsonl"
    old_file.write_text("{}\n", encoding="utf-8")
    new_file.write_text("{}\n", encoding="utf-8")

    now = datetime.now(timezone.utc)
    old_ts = (now - timedelta(days=8)).timestamp()
    new_ts = (now - timedelta(days=1)).timestamp()
    os.utime(old_file, (old_ts, old_ts))
    os.utime(new_file, (new_ts, new_ts))

    deleted = tl.cleanup_old_logs(now=now)

    assert deleted == 1
    assert not old_file.exists()
    assert new_file.exists()


def test_trace_logging_writes_retry_and_error_fallback_metadata(tmp_path, monkeypatch):
    import core.trace_logging as tl

    monkeypatch.setattr(tl, "TRACE_LOGGING_ENABLED", True)
    monkeypatch.setattr(tl, "TRACE_LOG_DIR", tmp_path)
    monkeypatch.setattr(tl, "TRACE_LOG_RETENTION_DAYS", 7)

    tl.initialize()
    tl.set_session_id("session-fallback")
    tl.start_turn("hello", mode="interactive")
    tl.start_llm_request(
        prompt="hello",
        context="",
        full_prompt="hello",
        attempt=1,
        provider="groq",
        model="groq:openai/gpt-oss-120b",
    )
    tl.log_llm_retry(
        reason="groq_token_limit_fallback",
        attempt=1,
        model="groq:openai/gpt-oss-120b",
        next_model="groq:llama-3.3-70b-versatile",
        attempted_models=["groq:openai/gpt-oss-120b"],
    )
    tl.log_llm_error(
        error="rate_limit_exceeded: token quota exceeded",
        attempt=3,
        model="groq:qwen/qwen3-32b",
        attempted_models=[
            "groq:openai/gpt-oss-120b",
            "groq:llama-3.3-70b-versatile",
            "groq:qwen/qwen3-32b",
        ],
        error_type="groq_token_limit_exhausted",
    )

    [log_file] = list(tmp_path.glob("trace-*.jsonl"))
    events = [json.loads(line) for line in log_file.read_text(encoding="utf-8").splitlines()]

    retry_event = [e for e in events if e["event"] == "llm_retry"][0]
    error_event = [e for e in events if e["event"] == "llm_error"][0]

    assert retry_event["reason"] == "groq_token_limit_fallback"
    assert retry_event["model"] == "groq:openai/gpt-oss-120b"
    assert retry_event["next_model"] == "groq:llama-3.3-70b-versatile"
    assert retry_event["attempted_models"] == ["groq:openai/gpt-oss-120b"]

    assert error_event["error_type"] == "groq_token_limit_exhausted"
    assert error_event["model"] == "groq:qwen/qwen3-32b"
    assert len(error_event["attempted_models"]) == 3
