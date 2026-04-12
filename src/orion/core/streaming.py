import re
import time
from typing import AsyncGenerator
from pydantic_ai import Agent
from rich.panel import Panel
from rich import box
from rich.panel import Panel
from rich import box
from orion.ui.renderer import (
    console, stream_response, print_system_info, print_system_error, print_system_warning
)
from orion.ui.spinner import Spinner
from orion import config
from orion.core import trace_logging as trace_logging
from orion.core.model_fallback import get_groq_token_limit_fallback_models

spinner = Spinner(console)

_TOOL_RETRY_HINT = (
    "\n\n[Important: Use tool calls directly — do not write function syntax in text.]"
)

_TEXTUAL_TOOL_CALL_RETRY_HINT = (
    "\n\n[Important: Your previous reply included literal function/tool-call text. "
    "Do NOT output any <function...>, tool_call, or JSON call payload in plain text. "
    "Execute tools via tool-calling and then return a normal user-facing answer.]"
)

_TEXTUAL_TOOL_CALL_PATTERNS = (
    re.compile(r"<\s*/?\s*function", re.IGNORECASE),
    re.compile(r"<\s*/?\s*tool_call", re.IGNORECASE),
)

_GROQ_TOKEN_LIMIT_PATTERNS = (
    re.compile(r"rate_limit_exceeded[^\n]*token", re.IGNORECASE),
    re.compile(r"token[^\n]*(limit|quota)[^\n]*(exceeded|reached)", re.IGNORECASE),
    re.compile(r"(request|prompt)[^\n]*(too large|too long)", re.IGNORECASE),
    re.compile(r"context length exceeded", re.IGNORECASE),
    re.compile(r"max[_\s-]?tokens", re.IGNORECASE),
)


def _looks_like_textual_tool_call(text: str) -> bool:
    """Detect obvious tool-call markup leaked into assistant text output."""
    return any(pattern.search(text) for pattern in _TEXTUAL_TOOL_CALL_PATTERNS)


def _is_groq_token_limit_error(error_text: str) -> bool:
    """Trigger fallback only for token-limit style Groq failures."""
    return any(pattern.search(error_text) for pattern in _GROQ_TOKEN_LIMIT_PATTERNS)


def _build_agent_for_model(model_string: str) -> Agent:
    from orion.core.agent import build_agent

    return build_agent(model_string_override=model_string)


async def _run_single_model(
    *,
    agent: Agent,
    prompt: str,
    context: str,
    base_prompt: str,
    model_name: str,
) -> tuple[str, str | None, bool, bool]:
    """
    Execute one model with existing per-model retry behavior.

    Returns:
      (response, error_text, token_limit_error, ok)
    """
    full_prompt = base_prompt
    full_response = ""

    for attempt in range(3):
        attempt_num = attempt + 1
        started = time.perf_counter()
        trace_logging.start_llm_request(
            prompt=prompt,
            context=context,
            full_prompt=full_prompt,
            attempt=attempt_num,
            provider=config.PROVIDER,
            model=model_name,
        )

        spinner.start("thinking")
        try:
            async with agent.run_stream(full_prompt) as result:
                await spinner.stop()

                async def live_tokens() -> AsyncGenerator[str, None]:
                    async for delta in result.stream_text(delta=True):
                        yield delta

                full_response = await stream_response(live_tokens())

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            trace_logging.log_llm_response(
                response=full_response,
                attempt=attempt_num,
                latency_ms=elapsed_ms,
            )

            if _looks_like_textual_tool_call(full_response) and attempt < 2:
                print_system_info("⟳ Detected leaked tool markup; retrying with guidance...")
                trace_logging.log_llm_retry(
                    reason="textual_tool_call_markup",
                    attempt=attempt_num,
                    model=model_name,
                )
                full_prompt = full_prompt + _TEXTUAL_TOOL_CALL_RETRY_HINT
                continue

            return full_response, None, False, True

        except Exception as e:
            await spinner.stop()
            err_str = str(e)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            trace_logging.log_llm_error(
                error=err_str,
                attempt=attempt_num,
                latency_ms=elapsed_ms,
                model=model_name,
            )

            if _is_groq_token_limit_error(err_str):
                return "", err_str, True, False

            if "failed_generation" in err_str and attempt < 2:
                # Groq XML/tool-call hallucination — retry with an explicit hint
                trace_logging.log_llm_retry(
                    reason="failed_generation",
                    attempt=attempt_num,
                    model=model_name,
                )
                full_prompt = full_prompt + _TOOL_RETRY_HINT
                continue

            print_system_error(err_str)
            return "", err_str, False, False

    return full_response, None, False, True


async def run_with_streaming(agent: Agent, prompt: str, context: str = "") -> str:
    """
    Run the agent and stream tokens live to the terminal.
    Shows tool activity in the spinner while tools are called.
    Returns the full assembled response text.
    Retries when providers return failed_generation errors or when the model
    leaks literal tool-call syntax (e.g. <function/...>) into plain text output.
    """
    base_prompt = f"{context}\n\n{prompt}" if context else prompt
    model_name = config.MODEL_STRING
    try:
        if config.PROVIDER != "groq":
            response, _error, _token_limit, _ok = await _run_single_model(
                agent=agent,
                prompt=prompt,
                context=context,
                base_prompt=base_prompt,
                model_name=model_name,
            )
            return response

        fallback_models = get_groq_token_limit_fallback_models()
        attempted_models: list[str] = []

        for model_index, fallback_model in enumerate(fallback_models):
            attempted_models.append(fallback_model)

            if fallback_model == model_name:
                current_agent = agent
            else:
                current_agent = _build_agent_for_model(fallback_model)

            response, err_str, token_limit_error, ok = await _run_single_model(
                agent=current_agent,
                prompt=prompt,
                context=context,
                base_prompt=base_prompt,
                model_name=fallback_model,
            )

            if ok:
                return response

            if token_limit_error:
                if model_index < len(fallback_models) - 1:
                    next_model = fallback_models[model_index + 1]
                    print_system_warning(f"Groq token limit hit. Falling back to {next_model}...")
                    trace_logging.log_llm_retry(
                        reason="groq_token_limit_fallback",
                        attempt=model_index + 1,
                        model=fallback_model,
                        next_model=next_model,
                        attempted_models=list(attempted_models),
                    )
                    continue

                msg = "Groq token limit exhausted across all fallback models."
                trace_logging.log_llm_error(
                    error=err_str or msg,
                    attempt=model_index + 1,
                    model=fallback_model,
                    attempted_models=list(attempted_models),
                    error_type="groq_token_limit_exhausted",
                )
                print_system_error(msg)
                return ""

            # Non-token-limit failure keeps existing behavior: no model fallback.
            return ""

        return ""
    finally:
        trace_logging.clear_request_id()
