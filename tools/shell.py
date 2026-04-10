import asyncio
import re
import shlex
from pathlib import Path
import subprocess
from safety.boundaries import validate_sudo
from safety import confirm

TIMEOUT = 30

_SHELL_REDIRECTION_TOKENS = {">", ">>", "1>", "1>>", "2>", "2>>"}
_COMMAND_SEPARATORS = {"&&", "||", ";", "|", "&"}
_DESTRUCTIVE_BINARIES = {"rm", "mv", "chmod", "chown", "chgrp", "truncate", "dd", "mkfs", "install"}
_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")

_SYSTEM_LEVEL_BINARIES = {
    "shutdown", "reboot", "poweroff", "halt", "init",
    "mount", "umount", "swapon", "swapoff",
    "useradd", "userdel", "usermod", "groupadd", "groupdel", "groupmod",
}


def _tokenize_shell(command: str) -> list[str]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|>")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        try:
            return shlex.split(command)
        except ValueError:
            return command.split()


def _split_shell_commands(command: str) -> list[list[str]]:
    tokens = _tokenize_shell(command)
    segments: list[list[str]] = []
    current: list[str] = []

    for token in tokens:
        if token in _COMMAND_SEPARATORS:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)

    if current:
        segments.append(current)
    return segments


def _extract_command_tokens(tokens: list[str]) -> list[str]:
    i = 0
    while i < len(tokens) and _ASSIGNMENT_RE.match(tokens[i]):
        i += 1
    return tokens[i:]


def _is_write_redirection_token(token: str) -> bool:
    if token in _SHELL_REDIRECTION_TOKENS:
        return True
    return re.fullmatch(r"\d?>>", token) is not None


def _is_destructive_git(tokens: list[str]) -> bool:
    if not tokens:
        return False
    sub = tokens[0]
    rest = tokens[1:]

    if sub == "reset" and any(flag in rest for flag in ("--hard", "--mixed", "--soft")):
        return True
    if sub == "clean" and any(flag in rest for flag in ("-f", "-fd", "-fdx", "-xdf", "-x")):
        return True
    if sub == "checkout" and "--" in rest:
        return True
    if sub == "restore" and any(flag in rest for flag in ("--staged", "--worktree", "--source")):
        return True
    if sub == "branch" and any(flag in rest for flag in ("-D", "--delete")):
        return True
    if sub == "tag" and "-d" in rest:
        return True
    if sub == "push" and any(flag in rest for flag in ("-f", "--force", "--force-with-lease")):
        return True
    return False


def _is_destructive_curl(tokens: list[str]) -> bool:
    if not tokens:
        return False

    lower_tokens = [t.lower() for t in tokens]
    short_write_flags = {"-d", "-F", "-T"}
    long_write_flags = {"--data", "--data-raw", "--data-binary", "--form", "--upload-file"}
    if any(t in short_write_flags for t in tokens) or any(t in long_write_flags for t in lower_tokens):
        return True

    for i, token in enumerate(tokens):
        if token in ("-X", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
            if method not in ("GET", "HEAD", "OPTIONS"):
                return True
    return False


def _is_destructive_system_command(binary: str, tokens: list[str]) -> bool:
    if binary in _SYSTEM_LEVEL_BINARIES:
        return True

    if binary == "systemctl":
        return any(
            op in tokens[1:]
            for op in ("start", "stop", "restart", "reload", "enable", "disable", "mask", "unmask", "kill")
        )

    if binary == "service":
        return any(op in tokens[1:] for op in ("start", "stop", "restart", "reload"))

    if binary in {"apt", "apt-get", "yum", "dnf", "pacman", "zypper"}:
        return any(
            op in tokens[1:]
            for op in (
                "install", "remove", "purge", "update", "upgrade", "full-upgrade",
                "dist-upgrade", "autoremove", "-S", "-R", "-Syu",
            )
        )

    if binary == "docker":
        if len(tokens) > 1 and tokens[1] in {"rm", "rmi", "stop", "kill", "restart", "compose", "system", "container", "volume", "network", "image"}:
            if tokens[1] == "compose":
                return len(tokens) > 2 and tokens[2] in {"down", "rm", "stop", "restart"}
            if tokens[1] in {"system", "container", "volume", "network", "image"}:
                return len(tokens) > 2 and tokens[2] in {"prune", "rm"}
            return True

    if binary == "kubectl":
        return len(tokens) > 1 and tokens[1] in {
            "delete", "apply", "replace", "patch", "scale", "drain", "cordon", "uncordon", "taint", "label", "annotate"
        }

    return False


def _requires_shell_confirmation(command: str) -> bool:
    for segment_tokens in _split_shell_commands(command):
        tokens = _extract_command_tokens(segment_tokens)
        if not tokens:
            continue

        binary = Path(tokens[0]).name.lower()
        if binary in _DESTRUCTIVE_BINARIES:
            return True
        if binary == "sed" and any(t == "-i" or t.startswith("-i") for t in tokens[1:]):
            return True
        if binary == "perl" and any(t == "-i" or t.startswith("-i") or t.startswith("-pi") for t in tokens[1:]):
            return True
        if binary == "find" and "-delete" in tokens:
            return True
        if binary == "git" and _is_destructive_git(tokens[1:]):
            return True
        if binary == "curl" and _is_destructive_curl(tokens[1:]):
            return True
        if _is_destructive_system_command(binary, tokens):
            return True

    all_tokens = _tokenize_shell(command)
    if any(_is_write_redirection_token(tok) for tok in all_tokens):
        return True
    return False


async def run_shell(command: str) -> str:
    """
    Execute a shell command safely and return its output.
    Use file tools (find_files, read_file, etc.) for file operations — only use this for everything else.
    Blocked: sudo, rm -rf, writes outside home.

    Args:
        command: The full shell command string to execute (e.g. 'ls -la', 'df -h', 'ps aux').
    """
    blocked, reason = validate_sudo(command)
    if blocked:
        return f"Blocked: {reason}"

    if _requires_shell_confirmation(command):
        confirmed = await confirm.ask_command_confirmation(command)
        if not confirmed.confirmed:
            if confirmed.repeated_denial:
                return (
                    "Shell command cancelled. Confirmation was already denied for this exact command in this turn. "
                    f"command={command}"
                )
            return (
                f"Shell command cancelled by user confirmation. command={command}"
            )

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
            cwd=str(Path.home()),
        )
        output = (result.stdout + result.stderr).strip()
        return output[:3000] if output else "(no output)"
    except subprocess.TimeoutExpired:
        return f"Command timed out after {TIMEOUT}s"
    except Exception as e:
        return f"Error: {e}"
