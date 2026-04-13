from dataclasses import dataclass
from typing import Literal

from prompt_toolkit import PromptSession
from rich.panel import Panel
from rich import box

DESTRUCTIVE_KEYWORDS = [
    "delete", "remove", "trash", "wipe", "clear",
    "overwrite", "replace", "format",
]

# We use a single module-level PromptSession. Since `parallel_tool_calls: False` is 
# configured in PydanticAI, tool executions (and thus confirmations) are strictly sequential.
# There is no risk of PromptSession re-entrancy from parallel tools.
_SESSION = PromptSession()

# This tracks denied actions to prevent redundant reprompting if an agent loops or retries.
# It is cleared at the beginning of every user turn via reset_turn_state(), ensuring
# memory is strictly bounded per-turn and does not leak across long sessions.
_denied_action_keys: set[str] = set()


@dataclass(frozen=True)
class ConfirmationResult:
    decision: Literal["confirmed", "denied"]
    scope: Literal["file", "shell"]
    action: str
    source_path: str | None = None
    destination_path: str | None = None
    command: str | None = None
    repeated_denial: bool = False

    @property
    def confirmed(self) -> bool:
        return self.decision == "confirmed"

    def __bool__(self) -> bool:
        return self.confirmed


def _normalize_action(value: str | None) -> str:
    return (value or "").strip().lower()


def _normalize_identity(value: str | None) -> str:
    return (value or "").strip()


def _make_action_key(
    *,
    scope: Literal["file", "shell"],
    action: str,
    source_path: str | None = None,
    destination_path: str | None = None,
    command: str | None = None,
) -> str:
    return "|".join(
        [
            scope,
            _normalize_action(action),
            _normalize_identity(source_path),
            _normalize_identity(destination_path),
            _normalize_identity(command),
        ]
    )


def reset_turn_state():
    _denied_action_keys.clear()


def requires_confirmation(action: str) -> bool:
    return any(keyword in action.lower() for keyword in DESTRUCTIVE_KEYWORDS)


async def ask_confirmation(description: str) -> bool:
    from orion.ui.renderer import console, pause_live, resume_live
    from orion.ui.spinner import stop_active_spinner

    await stop_active_spinner()
    pause_live()

    try:
        # Eliminate emojis entirely as they frequently cause width-calculation artifacts in many Linux terminals
        panel_body = f"[bold red]! ACTION REQUIRED[/bold red]\n\n{description}\n\n[dim]Type Y/Yes to confirm, anything else to cancel[/dim]"
        warning_panel = Panel(
            panel_body,
            title="[bold red]Safety Check[/bold red]",
            title_align="left",
            border_style="bold red",
            box=box.HEAVY,
            expand=True
        )

        console.print()
        console.print(warning_panel)
        from prompt_toolkit.formatted_text import HTML
        answer = await _SESSION.prompt_async(HTML("   <ansired><b>&gt;</b></ansired> "))
        return answer.strip().lower() in ("y", "yes")
    finally:
        resume_live()


async def ask_command_confirmation(command: str) -> ConfirmationResult:
    action_key = _make_action_key(
        scope="shell",
        action="run",
        command=command,
    )
    if action_key in _denied_action_keys:
        return ConfirmationResult(
            decision="denied",
            scope="shell",
            action="run",
            command=command,
            repeated_denial=True,
        )

    description = (
        "Run shell command:\n"
        f"  {command}"
    )
    confirmed = await ask_confirmation(description)
    if confirmed:
        return ConfirmationResult(
            decision="confirmed",
            scope="shell",
            action="run",
            command=command,
        )

    _denied_action_keys.add(action_key)
    return ConfirmationResult(
        decision="denied",
        scope="shell",
        action="run",
        command=command,
    )


async def ask_file_action_confirmation(
    action: str,
    *,
    source_path: str,
    destination_path: str | None = None,
) -> ConfirmationResult:
    action_lower = action.strip().lower()
    action_key = _make_action_key(
        scope="file",
        action=action_lower,
        source_path=source_path,
        destination_path=destination_path,
    )
    if action_key in _denied_action_keys:
        return ConfirmationResult(
            decision="denied",
            scope="file",
            action=action_lower,
            source_path=source_path,
            destination_path=destination_path,
            repeated_denial=True,
        )

    if action_lower == "delete":
        description = (
            "File Delete Confirmation\n"
            f"  path: {source_path}"
        )
    elif action_lower in ("move", "rename"):
        description = (
            f"File {action_lower.title()} Confirmation\n"
            f"  from: {source_path}\n"
            f"  to:   {destination_path or ''}"
        )
    else:
        description = (
            f"File Action Confirmation ({action})\n"
            f"  path: {source_path}"
        )

    confirmed = await ask_confirmation(description)
    if confirmed:
        return ConfirmationResult(
            decision="confirmed",
            scope="file",
            action=action_lower,
            source_path=source_path,
            destination_path=destination_path,
        )

    _denied_action_keys.add(action_key)
    return ConfirmationResult(
        decision="denied",
        scope="file",
        action=action_lower,
        source_path=source_path,
        destination_path=destination_path,
    )