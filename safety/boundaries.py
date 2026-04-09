import shlex
from pathlib import Path

HOME = Path.home()

BLOCKED_COMMANDS = ["sudo", "su", "pkexec", "doas"]

DANGER_PATTERNS = [
    "rm -rf", "rm -r /", "chmod -R 777",
    "dd if=", "> /dev/", "mkfs", ":(){ :|:& };:"
]

def validate_path(path: str) -> tuple[bool, str]:
    try:
        resolved = Path(path).expanduser().resolve()
        resolved.relative_to(HOME)
        return True, str(resolved)
    except ValueError:
        return False, f"Blocked: '{path}' is outside your home directory."
    except Exception as e:
        return False, f"Invalid path '{path}': {e}"

def validate_sudo(command: str) -> tuple[bool, str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        tokens = command.split()

    for blocked in BLOCKED_COMMANDS:
        if blocked in tokens:
            return True, "sudo/root commands are not permitted."

    for pattern in DANGER_PATTERNS:
        if pattern in command:
            return True, f"Dangerous pattern detected: '{pattern}'"

    return False, ""
