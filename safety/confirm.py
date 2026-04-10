from prompt_toolkit import PromptSession

DESTRUCTIVE_KEYWORDS = [
    "delete", "remove", "trash", "wipe", "clear",
    "overwrite", "replace", "format",
]

_SESSION = PromptSession()


def requires_confirmation(action: str) -> bool:
    return any(keyword in action.lower() for keyword in DESTRUCTIVE_KEYWORDS)


async def ask_confirmation(description: str) -> bool:
    from ui.renderer import console

    console.print()
    console.print(f"[warning]⚠  {description}[/warning]")
    console.print("[dim]Type yes to confirm, anything else to cancel[/dim]")
    answer = await _SESSION.prompt_async("  ❯ ")
    return answer.strip().lower() in ("yes", "y")