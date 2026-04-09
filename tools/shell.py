import subprocess
from safety.boundaries import validate_sudo

TIMEOUT = 30


async def run_shell(command: str) -> str:
    """
    Execute a shell command safely.
    Use manage_files for file operations — this is for everything else.
    Blocked: sudo, rm -rf, writes outside home.
    """
    blocked, reason = validate_sudo(command)
    if blocked:
        return f"Blocked: {reason}"

    try:
        result = subprocess.run(
            command, shell=True,
            capture_output=True, text=True,
            timeout=TIMEOUT,
            cwd=str(__import__("pathlib").Path.home())
        )
        output = (result.stdout + result.stderr).strip()
        return output[:3000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {TIMEOUT}s"
    except Exception as e:
        return f"Error: {e}"
