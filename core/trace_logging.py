from __future__ import annotations

import json
import threading
import uuid
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone
from pathlib import Path

from config import TRACE_LOGGING_ENABLED, TRACE_LOG_DIR, TRACE_LOG_RETENTION_DAYS

_write_lock = threading.Lock()
_sequence_lock = threading.Lock()
_sequence = 0

_session_id_var: ContextVar[str | None] = ContextVar("trace_session_id", default=None)
_turn_id_var: ContextVar[str | None] = ContextVar("trace_turn_id", default=None)
_request_id_var: ContextVar[str | None] = ContextVar("trace_request_id", default=None)


def initialize() -> None:
    if not TRACE_LOGGING_ENABLED:
        return
    TRACE_LOG_DIR.mkdir(parents=True, exist_ok=True)


def set_session_id(session_id: str) -> None:
    _session_id_var.set(session_id)


def start_turn(user_input: str, mode: str) -> str:
    turn_id = str(uuid.uuid4())
    _turn_id_var.set(turn_id)
    _request_id_var.set(None)
    log_event("turn_start", mode=mode, user_input=user_input)
    return turn_id


def end_turn(*, status: str, assistant_response: str | None = None, error: str | None = None, latency_ms: int | None = None) -> None:
    payload: dict[str, object] = {"status": status}
    if assistant_response is not None:
        payload["assistant_response"] = assistant_response
    if error is not None:
        payload["error"] = error
    if latency_ms is not None:
        payload["latency_ms"] = latency_ms

    log_event("turn_end", **payload)
    _request_id_var.set(None)
    _turn_id_var.set(None)


def start_llm_request(*, prompt: str, context: str, full_prompt: str, attempt: int, provider: str, model: str) -> str:
    request_id = str(uuid.uuid4())
    _request_id_var.set(request_id)
    log_event(
        "llm_request",
        attempt=attempt,
        provider=provider,
        model=model,
        prompt=prompt,
        context=context,
        full_prompt=full_prompt,
    )
    return request_id


def log_llm_response(*, response: str, attempt: int, latency_ms: int, finish_reason: str = "completed") -> None:
    log_event(
        "llm_response",
        attempt=attempt,
        response=response,
        latency_ms=latency_ms,
        finish_reason=finish_reason,
    )


def log_llm_retry(
    *,
    reason: str,
    attempt: int,
    model: str | None = None,
    next_model: str | None = None,
    attempted_models: list[str] | None = None,
) -> None:
    payload: dict[str, object] = {"reason": reason, "attempt": attempt}
    if model is not None:
        payload["model"] = model
    if next_model is not None:
        payload["next_model"] = next_model
    if attempted_models is not None:
        payload["attempted_models"] = attempted_models
    log_event("llm_retry", **payload)


def log_llm_error(
    *,
    error: str,
    attempt: int,
    latency_ms: int | None = None,
    model: str | None = None,
    attempted_models: list[str] | None = None,
    error_type: str | None = None,
) -> None:
    payload: dict[str, object] = {"error": error, "attempt": attempt}
    if latency_ms is not None:
        payload["latency_ms"] = latency_ms
    if model is not None:
        payload["model"] = model
    if attempted_models is not None:
        payload["attempted_models"] = attempted_models
    if error_type is not None:
        payload["error_type"] = error_type
    log_event("llm_error", **payload)


def clear_request_id() -> None:
    _request_id_var.set(None)


def log_tool_call_start(*, tool_name: str, args: tuple, kwargs: dict) -> str:
    tool_call_id = str(uuid.uuid4())
    log_event(
        "tool_call_start",
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        parameters={"args": args, "kwargs": kwargs},
    )
    return tool_call_id


def log_tool_call_end(
    *,
    tool_call_id: str,
    tool_name: str,
    status: str,
    result: object | None = None,
    error: str | None = None,
    elapsed_ms: int,
) -> None:
    payload: dict[str, object] = {
        "tool_call_id": tool_call_id,
        "tool_name": tool_name,
        "status": status,
        "elapsed_ms": elapsed_ms,
    }
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error

    log_event("tool_call_end", **payload)


def cleanup_old_logs(now: datetime | None = None) -> int:
    if not TRACE_LOGGING_ENABLED:
        return 0

    initialize()
    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(days=TRACE_LOG_RETENTION_DAYS)
    deleted = 0

    for path in TRACE_LOG_DIR.glob("trace-*.jsonl"):
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified < cutoff:
                path.unlink(missing_ok=True)
                deleted += 1
        except OSError:
            continue

    return deleted


def log_event(event_type: str, **payload: object) -> None:
    if not TRACE_LOGGING_ENABLED:
        return

    initialize()

    event = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event_type,
        "seq": _next_sequence(),
        "session_id": _session_id_var.get(),
        "turn_id": _turn_id_var.get(),
        "request_id": _request_id_var.get(),
        **payload,
    }

    line = json.dumps(event, ensure_ascii=False, default=_json_default)

    try:
        with _write_lock:
            with _log_file_for_today().open("a", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")
    except OSError:
        # Tracing must never break runtime flow.
        return


def _next_sequence() -> int:
    global _sequence
    with _sequence_lock:
        _sequence += 1
        return _sequence


def _json_default(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _log_file_for_today() -> Path:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return TRACE_LOG_DIR / f"trace-{day}.jsonl"
