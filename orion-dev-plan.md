# Orion — Development Plan

**Invoke:** `orion open the latest markiplier video`  
**Stack:** PydanticAI · Ollama + Qwen3-8B/4B · SQLite + sqlite-vec · Rich + prompt_toolkit  
**Hardware target:** 16GB RAM · RTX 1650/3050 (4GB VRAM) · Linux  
**Philosophy:** Minimal yet beautiful — purposeful, not cluttered  
**Theme:** Catppuccin Mocha

---

## Project Structure

```text
~/.orion/
├── memory.db                      ← SQLite database
├── history                        ← prompt_toolkit input history
└── config.toml                    ← user overrides (optional)

~/Programming/Projects/cli-assistant/
├── main.py                        ← entry point
├── config.py                      ← constants and settings
├── pyproject.toml                 ← dependencies (managed by uv)
│
├── core/
│   ├── agent.py                   ← PydanticAI agent setup
│   ├── context.py                 ← 3-tier context assembly
│   ├── router.py                  ← model selection (8B vs 4B)
│   └── streaming.py               ← live token stream → Rich renderer
│
├── memory/
│   ├── db.py                      ← SQLite connection + migrations
│   ├── store.py                   ← read/write turns, profile facts
│   ├── retrieval.py               ← hybrid FTS5 + sqlite-vec search
│   ├── embeddings.py              ← nomic-embed-text via Ollama
│   ├── indexer.py                 ← home directory file scanner
│   └── extractor.py               ← auto-extract profile facts from turns
│
├── tools/
│   ├── files.py                   ← file management
│   ├── shell.py                   ← safe shell execution
│   ├── browser.py                 ← xdg-open + Trafilatura + Playwright
│   ├── search.py                  ← DuckDuckGo web search
│   └── media.py                   ← YouTube / media search and open
│
├── ui/
│   ├── renderer.py                ← Rich console, Catppuccin theme, Markdown
│   ├── input.py                   ← prompt_toolkit session with history
│   ├── spinner.py                 ← Braille dot activity display
│   └── startup.py                 ← startup screen with system checks
│
└── safety/
    ├── boundaries.py              ← path validation, sudo block
    └── confirm.py                 ← confirmation prompts for destructive ops
```

---

## Build Stages

Build and test each stage independently before moving to the next.  
Never move forward with a broken stage — the stages are load-bearing.

```text
Stage 1 — Inference baseline        (1–2 days)
Stage 2 — Minimal UI shell          (1–2 days)
Stage 3 — Agent + tools             (2–3 days)
Stage 4 — Memory layer              (2–3 days)
Stage 5 — Web + media tools         (1–2 days)
Stage 6 — Safety layer              (1 day)
Stage 7 — Polish + UX details       (1–2 days)
──────────────────────────────────────────────
Total estimated time:               9–15 days
```

---

## Stage 1 — Inference Baseline

**Goal:** Ollama running, Qwen3 responding, tokens streaming live to terminal. Nothing else.

### Setup

```bash
curl -fsSL https://ollama.com/install.sh | sh
systemctl enable ollama
systemctl start ollama

ollama pull qwen3:4b
ollama pull nomic-embed-text

echo 'OLLAMA_FLASH_ATTENTION=1' >> /etc/ollama/ollama.env
echo 'OLLAMA_MAX_LOADED_MODELS=1' >> /etc/ollama/ollama.env
echo 'OLLAMA_NUM_PARALLEL=1' >> /etc/ollama/ollama.env
systemctl restart ollama
```

### config.py

```python
import tomllib
from pathlib import Path

HOME          = Path.home()
ORION_DIR     = HOME / ".orion"
DB_PATH       = ORION_DIR / "memory.db"
HISTORY_FILE  = ORION_DIR / "history"
CONFIG_FILE   = ORION_DIR / "config.toml"

# Defaults — can be overridden by ~/.orion/config.toml
_defaults = {
    "model_primary": "qwen3:4b",
    "model_fast":    "qwen3:4b",
    "theme":         "mocha",
    "max_width":     100,
}

def _load_user_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "rb") as f:
            return tomllib.load(f)
    return {}

_user = _load_user_config()

MODEL_PRIMARY = _user.get("model_primary", _defaults["model_primary"])
MODEL_FAST    = _user.get("model_fast",    _defaults["model_fast"])
THEME         = _user.get("theme",         _defaults["theme"])
MAX_WIDTH     = _user.get("max_width",     _defaults["max_width"])

OLLAMA_BASE        = "http://localhost:11434/v1"
OLLAMA_API_BASE    = "http://localhost:11434"
EMBED_MODEL        = "nomic-embed-text"
EMBED_DIM          = 256

# keep_alive values sent with every Ollama request
KEEP_ALIVE_ACTIVE  = "10m"
KEEP_ALIVE_IDLE    = "2m"
KEEP_ALIVE_BATTERY = "30s"

# Context window budget (tokens)
CONTEXT_PROFILE   = 800
CONTEXT_RECENT    = 2000
CONTEXT_RETRIEVED = 2000
CONTEXT_RESERVE   = 3000
```

### Test: bare streaming inference

```python
# test_stage1.py
import asyncio
from openai import AsyncOpenAI

client = AsyncOpenAI(base_url="http://localhost:11434/v1", api_key="ollama")

async def test():
    stream = await client.chat.completions.create(
        model="qwen3:4b",
        messages=[{"role": "user", "content": "Say hello in 10 words"}],
        stream=True,
        extra_body={"think": False, "keep_alive": "10m"}
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            print(delta, end="", flush=True)
    print()

asyncio.run(test())
```

**Pass condition:** Tokens appear one by one within ~1–2 seconds at 5–8 t/s.

---

## Stage 2 — Minimal UI Shell

**Goal:** Full terminal look and feel. Input → echo → styled output. No agent yet. Model pre-warm happens here so first real query has no cold-start delay.

### Stage 2 dependencies

```bash
uv add rich prompt_toolkit httpx
```

### ui/renderer.py

```python
import shutil
from rich.console import Console
from rich.theme import Theme
from rich.markdown import Markdown
from rich.live import Live
from rich.text import Text

MOCHA = Theme({
    "user":      "bold #CDD6F4",
    "assistant": "#89DCEB",
    "dim":       "#6C7086",
    "thinking":  "italic #585B70",
    "success":   "#A6E3A1",
    "warning":   "#F9E2AF",
    "error":     "#F38BA8",
    "accent":    "#89B4FA",
    "border":    "#313244",
    "muted":     "#45475A",
})

console = Console(
    theme=MOCHA,
    highlight=False,
    width=min(shutil.get_terminal_size().columns, 100)
)

def print_user(text: str):
    console.print("[dim]you[/dim]")
    console.print(f"[user]{text}[/user]")
    console.print()

def print_separator():
    console.print(f"[border]{'─' * console.width}[/border]")

async def stream_response(token_gen) -> str:
    """
    Stream tokens live with Markdown rendering.
    token_gen must be an async generator yielding string deltas.
    Returns the full assembled response.
    """
    content = ""
    console.print("[dim]orion[/dim]")

    with Live(
        Markdown(""),
        console=console,
        refresh_per_second=15,
        transient=False
    ) as live:
        async for token in token_gen:
            content += token
            live.update(Markdown(content))

    console.print()
    return content
```

### ui/spinner.py

```python
import asyncio
import itertools
from rich.console import Console

BRAILLE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

class Spinner:
    """Asyncio-native spinner — no threads, no race conditions with asyncio."""

    def __init__(self, console: Console):
        self.console = console
        self._label = "thinking"
        self._task: asyncio.Task | None = None

    def start(self, label: str = "thinking"):
        """Call from async context. Creates a background asyncio task."""
        self._label = label
        self._task  = asyncio.create_task(self._spin())

    def update(self, label: str):
        self._label = label

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.console.print("\r" + " " * 60 + "\r", end="")

    async def _spin(self):
        for frame in itertools.cycle(BRAILLE):
            self.console.print(
                f"\r[thinking]{frame} {self._label}[/thinking]",
                end="", highlight=False
            )
            await asyncio.sleep(0.08)
```

### ui/input.py

```python
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from config import HISTORY_FILE

def build_session() -> PromptSession:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    bindings = KeyBindings()

    @bindings.add("c-l")
    def clear_screen(event):
        event.app.renderer.clear()

    @bindings.add("c-c")
    def interrupt(event):
        raise KeyboardInterrupt

    return PromptSession(
        history=FileHistory(str(HISTORY_FILE)),
        auto_suggest=AutoSuggestFromHistory(),
        key_bindings=bindings,
        multiline=False,
        enable_open_in_editor=True,
    )

def get_prompt_text(model: str = "qwen3-8b") -> HTML:
    return HTML(f'<ansibrightblack>{model}</ansibrightblack> <ansiblue>❯</ansiblue> ')

async def get_input(session: PromptSession, model: str) -> str:
    return await session.prompt_async(get_prompt_text(model))
```

### ui/startup.py

```python
import asyncio
import httpx
from rich.console import Console
from rich.text import Text
from config import OLLAMA_API_BASE, OLLAMA_BASE, MODEL_PRIMARY, DB_PATH

def show_startup(console: Console, model: str):
    console.clear()

    wordmark = Text()
    wordmark.append("  ◆ ", style="#89B4FA bold")
    wordmark.append("orion", style="#CDD6F4 bold")
    wordmark.append(f"  {model}", style="#6C7086")

    console.print()
    console.print(wordmark)
    console.print("  [#6C7086]" + "─" * 40 + "[/#6C7086]")
    console.print("  [#6C7086]offline · local · private[/#6C7086]")
    console.print()

    checks = [
        ("ollama",  _check_ollama()),
        ("memory",  _check_db()),
        ("index",   _check_index()),
    ]

    for name, ok in checks:
        dot = "[#A6E3A1]●[/#A6E3A1]" if ok else "[#F38BA8]●[/#F38BA8]"
        console.print(f"  {dot} [#6C7086]{name}[/#6C7086]")

    console.print()

def _check_ollama() -> bool:
    try:
        r = httpx.get(f"{OLLAMA_API_BASE}/api/tags", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def _check_db() -> bool:
    return DB_PATH.exists()

def _check_index() -> bool:
    if not DB_PATH.exists():
        return False
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        count = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False

async def prewarm_model(model: str):
    """Pre-load the model so first real query has no cold-start delay."""
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{OLLAMA_API_BASE}/api/generate",
                json={"model": model, "prompt": "", "keep_alive": "10m"},
                timeout=30
            )
    except Exception:
        pass  # non-fatal — just means first query will be slower
```

### main.py skeleton (Stages 1–2)

```python
import asyncio
import sys
from ui.renderer import console, print_user, print_separator, stream_response
from ui.input import build_session, get_input
from ui.startup import show_startup, prewarm_model
from config import MODEL_PRIMARY

async def main():
    # One-shot mode: orion open the latest markiplier video
    if len(sys.argv) > 1 and sys.stdin.isatty():
        query = " ".join(sys.argv[1:])
        await run_once(query)
        return

    show_startup(console, MODEL_PRIMARY)
    await prewarm_model(MODEL_PRIMARY)

    session = build_session()

    while True:
        try:
            user_input = await get_input(session, MODEL_PRIMARY)
            if not user_input.strip():
                continue
            if user_input.strip() in ("/exit", "/quit", "exit", "quit"):
                break

            await run_once(user_input)

        except KeyboardInterrupt:
            console.print("\n[#6C7086]Interrupted.[/#6C7086]")
        except EOFError:
            break

async def run_once(query: str):
    print_user(query)

    # Stages 1–2: echo back. Replaced with real agent in Stage 3.
    async def fake_stream():
        for word in f"You said: {query}".split():
            yield word + " "

    await stream_response(fake_stream())
    print_separator()

if __name__ == "__main__":
    asyncio.run(main())
```

**Pass condition:** `python main.py` → startup screen → prompt → styled echo. `python main.py tell me a joke` → one-shot echo → exits. No crashes.

---

## Stage 3 — Agent + Tools

**Goal:** PydanticAI agent wired to Ollama. Core tools working. Live token streaming. Tool activity shown in spinner.

### Stage 3 dependencies

```bash
uv add pydantic-ai
```

### core/agent.py

```python
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from config import OLLAMA_BASE, MODEL_PRIMARY, KEEP_ALIVE_ACTIVE
import os
from pathlib import Path

def build_agent(model_name: str = MODEL_PRIMARY, think: bool = False) -> Agent:
    model = OpenAIModel(
        model_name,
        provider=OpenAIProvider(
            base_url=OLLAMA_BASE,
            api_key="ollama"
        )
    )

    agent = Agent(
        model=model,
        system_prompt=_build_system_prompt(),
        model_settings={
            "extra_body": {
                "think": think,
                "keep_alive": KEEP_ALIVE_ACTIVE
            }
        }
    )

    from tools.files import manage_files
    from tools.shell import run_shell
    from tools.browser import open_url, fetch_page
    from tools.search import web_search
    from tools.media import open_media

    for tool in [manage_files, run_shell, open_url, fetch_page, web_search, open_media]:
        agent.tool_plain(tool)

    return agent

def _build_system_prompt() -> str:
    cwd   = os.getcwd()
    shell = os.environ.get("SHELL", "bash")
    home  = Path.home()
    return f"""You are Orion, a local AI assistant running entirely offline on Linux.

ENVIRONMENT:
- Current directory: {cwd}
- Shell: {shell}
- Home: {home}
- OS: Linux

RULES:
- Never guess file paths. Always call manage_files(action="find") first to locate files.
- For destructive operations (delete, overwrite), always confirm with the user first.
- Never run sudo commands. Never touch paths outside {home}.
- Be concise. No padding. No "As an AI..." disclaimers.
- Respond in plain Markdown. No HTML.
- When opening media or YouTube content, use open_media — not a raw URL.
"""
```

### core/router.py

```python
from config import MODEL_PRIMARY, MODEL_FAST

# Queries that need reasoning or generation → 8B
THINK_TRIGGERS = [
    "explain", "summarize", "analyze", "research", "write", "draft",
    "plan", "compare", "why", "how does", "what is", "describe",
    "review", "suggest", "recommend"
]

def select_model(query: str) -> str:
    """
    Use 4B for simple tool-dispatch queries.
    Use 8B whenever reasoning or generation is likely needed.
    Default to 8B when uncertain.
    """
    q = query.lower()
    if any(t in q for t in THINK_TRIGGERS):
        return MODEL_PRIMARY
    # Simple tool-dispatch: open, find, list, move, rename, search, show
    return MODEL_FAST
```

### core/streaming.py

```python
import asyncio
from typing import AsyncGenerator
from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelRequest, ModelResponse, ToolCallPart, ToolReturnPart
)
from ui.renderer import console, stream_response
from ui.spinner import Spinner

spinner = Spinner(console)

async def run_with_streaming(agent: Agent, prompt: str, context: str = "") -> str:
    """
    Run the agent and stream tokens live to the terminal.
    Shows tool activity in the spinner as tools are called.
    """
    full_prompt = f"{context}\n\n{prompt}" if context else prompt
    full_response = ""
    spinner.start("thinking")

    try:
        async with agent.run_stream(full_prompt) as result:
            # Watch for tool call events and update spinner label
            async def watch_messages():
                async for msg in result.stream_messages():
                    if isinstance(msg, ModelResponse):
                        for part in msg.parts:
                            if isinstance(part, ToolCallPart):
                                spinner.update(f"calling {part.tool_name}…")

            watcher = asyncio.create_task(watch_messages())

            # Live-stream tokens as they arrive
            async def live_tokens() -> AsyncGenerator[str, None]:
                await spinner.stop()
                async for delta in result.stream_text(delta=True):
                    yield delta

            full_response = await stream_response(live_tokens())
            watcher.cancel()

    except Exception as e:
        await spinner.stop()
        console.print(f"[error]Error: {e}[/error]")

    return full_response
```

### tools/files.py

```python
import os
import shutil
import subprocess
from pathlib import Path
from pydantic_ai import RunContext
from safety.boundaries import validate_path

HOME = Path.home()

async def manage_files(
    action: str,
    path: str = "",
    destination: str = "",
    query: str = "",
) -> str:
    """
    Unified file management. Actions: find | list | open | read | move | rename | delete | create.
    Always call action='find' first to locate a file before operating on it.
    """
    if action == "find":
        return _find_files(query or path)

    if action == "list":
        target = Path(path) if path else HOME
        ok, resolved = validate_path(str(target))
        if not ok:
            return resolved
        items = sorted(Path(resolved).iterdir()) if Path(resolved).is_dir() else []
        return "\n".join(str(i) for i in items[:50])

    if action == "open":
        ok, resolved = validate_path(path)
        if not ok:
            return resolved
        if not Path(resolved).exists():
            return f"Not found: {path}. Try action='find' first."
        subprocess.Popen(["xdg-open", resolved])
        return f"Opened {Path(resolved).name}"

    if action == "read":
        ok, resolved = validate_path(path)
        if not ok:
            return resolved
        try:
            return Path(resolved).read_text(errors="replace")[:4000]
        except Exception as e:
            return f"Error reading {path}: {e}"

    if action == "move":
        ok, src = validate_path(path)
        if not ok:
            return src
        ok, dst = validate_path(destination)
        if not ok:
            return dst
        shutil.move(src, dst)
        _log_operation("move", src, dst)
        return f"Moved {Path(src).name} → {dst}"

    if action == "rename":
        ok, src = validate_path(path)
        if not ok:
            return src
        new_path = str(Path(src).parent / destination)
        ok, dst = validate_path(new_path)
        if not ok:
            return dst
        os.rename(src, dst)
        _log_operation("rename", src, dst)
        return f"Renamed to {destination}"

    if action == "delete":
        ok, resolved = validate_path(path)
        if not ok:
            return resolved
        subprocess.run(["gio", "trash", resolved])
        _log_operation("delete", resolved, "trash")
        return f"Moved to trash: {Path(resolved).name}"

    if action == "create":
        ok, resolved = validate_path(path)
        if not ok:
            return resolved
        p = Path(resolved)
        if path.endswith("/"):
            p.mkdir(parents=True, exist_ok=True)
            return f"Created folder: {resolved}"
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("")
            return f"Created file: {resolved}"

    return f"Unknown action: {action}"


def _find_files(query: str) -> str:
    """Search using the SQLite index (Stage 4+), falls back to find."""
    if not query:
        return "Provide a query or path to search."
    try:
        # Stage 4+ will query the SQLite files table here
        from pathlib import Path
        out = subprocess.run(
            ["find", str(HOME), "-iname", f"*{query}*",
             "-not", "-path", "*/.*", "-maxdepth", "8"],
            capture_output=True, text=True, timeout=5
        )
        results = [r for r in out.stdout.strip().split("\n") if r][:10]
    except subprocess.TimeoutExpired:
        return "Search timed out. Try being more specific."
    return "\n".join(results) or f"No files found matching '{query}'"


def _log_operation(op: str, src: str, dst: str):
    """Log to operation_log in SQLite (wired in Stage 4)."""
    pass
```

### tools/shell.py

```python
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
```

### safety/boundaries.py

```python
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
```

### Update main.py for Stage 3

```python
import asyncio
import sys
import uuid
from ui.renderer import console, print_user, print_separator
from ui.input import build_session, get_input
from ui.startup import show_startup, prewarm_model
from core.agent import build_agent
from core.router import select_model
from core.streaming import run_with_streaming
from config import MODEL_PRIMARY

session_id = str(uuid.uuid4())
current_model = MODEL_PRIMARY
think_mode = False
agent = build_agent(current_model, think=think_mode)

async def main():
    global agent, current_model, think_mode

    # One-shot: orion open the latest markiplier video
    if len(sys.argv) > 1 and sys.stdin.isatty() and sys.argv[1] != "--init":
        query = " ".join(sys.argv[1:])
        await run_once(query)
        return

    # Pipe mode: cat log.txt | orion "what went wrong?"
    if not sys.stdin.isatty():
        piped_input = sys.stdin.read()
        user_query = sys.argv[1] if len(sys.argv) > 1 else "Analyze this:"
        full_query = f"{user_query}\n\n```\n{piped_input[:4000]}\n```"
        response = await run_with_streaming(agent, full_query)
        print(response)
        return

    show_startup(console, current_model)
    await prewarm_model(current_model)
    session = build_session()

    while True:
        try:
            user_input = await get_input(session, current_model)
            if not user_input.strip():
                continue
            if user_input.strip() in ("/exit", "/quit", "exit", "quit"):
                break
            if user_input.startswith("/"):
                await handle_slash(user_input)
                continue

            await run_once(user_input)

        except KeyboardInterrupt:
            console.print("\n[#6C7086]Interrupted.[/#6C7086]")
        except EOFError:
            break

async def run_once(query: str):
    global agent, current_model
    model = select_model(query)
    if model != current_model:
        current_model = model
        agent = build_agent(current_model, think=think_mode)

    print_user(query)
    await run_with_streaming(agent, query)
    print_separator()

async def handle_slash(cmd: str):
    # Slash commands wired fully in Stage 7
    console.print(f"[dim]{cmd} — slash commands active in Stage 7[/dim]")

if __name__ == "__main__":
    asyncio.run(main())
```

**Pass condition:** `orion list files in downloads` → agent calls `manage_files(action="list")` → real file list. `orion what is the capital of France` → direct LLM answer streams token by token. Spinner shows tool name while tool runs.

---

## Stage 4 — Memory Layer

**Goal:** SQLite + sqlite-vec for persistent memory. Conversation saving. File indexer. 3-tier context injection. Profile auto-extraction.

### Stage 4 dependencies

```bash
uv add sqlite-vec
# nomic-embed-text already pulled in Stage 1
```

### memory/db.py

```python
import sqlite3
import sqlite_vec
from config import DB_PATH

def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    sqlite_vec.load(conn)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _run_migrations(conn)
    return conn

def _run_migrations(conn: sqlite3.Connection):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id          INTEGER PRIMARY KEY,
            session_id  TEXT NOT NULL,
            role        TEXT NOT NULL,
            content     TEXT NOT NULL,
            timestamp   TEXT DEFAULT (datetime('now')),
            tool_calls  TEXT
        );

        CREATE TABLE IF NOT EXISTS user_profile (
            key         TEXT PRIMARY KEY,
            value       TEXT NOT NULL,
            updated_at  TEXT DEFAULT (datetime('now')),
            confidence  REAL DEFAULT 1.0
        );

        CREATE TABLE IF NOT EXISTS files (
            id          INTEGER PRIMARY KEY,
            path        TEXT UNIQUE NOT NULL,
            name        TEXT NOT NULL,
            extension   TEXT,
            size_kb     INTEGER,
            modified_at TEXT,
            tags        TEXT
        );

        CREATE TABLE IF NOT EXISTS operation_log (
            id          INTEGER PRIMARY KEY,
            operation   TEXT NOT NULL,
            source      TEXT,
            destination TEXT,
            timestamp   TEXT DEFAULT (datetime('now'))
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            content, key, source,
            tokenize='porter unicode61'
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS vec_memory USING vec0(
            embedding float[256]
        );

        CREATE TABLE IF NOT EXISTS vec_meta (
            rowid       INTEGER PRIMARY KEY,
            content     TEXT,
            source      TEXT,
            source_id   INTEGER
        );
    """)
    conn.commit()
```

### memory/store.py

```python
import json
import sqlite3
from config import CONTEXT_RECENT

def save_turn(conn: sqlite3.Connection, session_id: str, role: str,
              content: str, tool_calls: list | None = None):
    conn.execute(
        """INSERT INTO conversations (session_id, role, content, tool_calls)
           VALUES (?, ?, ?, ?)""",
        (session_id, role, content, json.dumps(tool_calls) if tool_calls else None)
    )
    conn.commit()

def get_recent_turns(conn: sqlite3.Connection, session_id: str,
                     max_tokens: int = CONTEXT_RECENT) -> str:
    rows = conn.execute(
        """SELECT role, content FROM conversations
           WHERE session_id = ?
           ORDER BY id DESC LIMIT 20""",
        (session_id,)
    ).fetchall()

    lines = []
    total = 0
    for row in reversed(rows):
        entry = f"{row['role'].upper()}: {row['content']}"
        total += len(entry.split())
        if total > max_tokens:
            break
        lines.append(entry)

    return "\n".join(lines)

def upsert_profile(conn: sqlite3.Connection, key: str, value: str,
                   confidence: float = 1.0):
    conn.execute(
        """INSERT INTO user_profile (key, value, confidence)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET
               value      = excluded.value,
               confidence = excluded.confidence,
               updated_at = datetime('now')""",
        (key, value, confidence)
    )
    conn.commit()

def get_user_profile(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT key, value FROM user_profile ORDER BY confidence DESC"
    ).fetchall()
    return {row["key"]: row["value"] for row in rows}

def log_operation(conn: sqlite3.Connection, operation: str,
                  source: str, destination: str):
    conn.execute(
        """INSERT INTO operation_log (operation, source, destination)
           VALUES (?, ?, ?)""",
        (operation, source, destination)
    )
    conn.commit()

def get_last_operation(conn: sqlite3.Connection) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM operation_log ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
```

### memory/embeddings.py

```python
import struct
import httpx
from config import OLLAMA_API_BASE, EMBED_MODEL, EMBED_DIM

async def embed(text: str) -> list[float]:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{OLLAMA_API_BASE}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=10
        )
        full_vector = r.json()["embedding"]
        return full_vector[:EMBED_DIM]

def serialize(floats: list[float]) -> bytes:
    return struct.pack(f"{len(floats)}f", *floats)
```

### memory/retrieval.py

```python
import sqlite3
from memory.embeddings import embed, serialize

RECALL_SIGNALS = [
    "remember", "earlier", "yesterday", "last time",
    "you said", "i told you", "we discussed",
    " it ", " that ", " the one", " my "
]

def should_retrieve(query: str) -> bool:
    q = query.lower()
    return any(signal in q for signal in RECALL_SIGNALS)

async def hybrid_search(conn: sqlite3.Connection, query: str, k: int = 5) -> list[dict]:
    """Reciprocal Rank Fusion over FTS5 keyword + sqlite-vec semantic results."""
    fts_results = conn.execute(
        """SELECT rowid, content, bm25(memory_fts) as score
           FROM memory_fts WHERE memory_fts MATCH ?
           ORDER BY score LIMIT 20""",
        (query,)
    ).fetchall()

    query_vec = await embed(query)
    vec_results = conn.execute(
        """SELECT rowid, distance FROM vec_memory
           WHERE embedding MATCH ?
           ORDER BY distance LIMIT 20""",
        (sqlite3.Binary(serialize(query_vec)),)
    ).fetchall()

    rrf_scores: dict[int, float] = {}
    RRF_K = 60

    for rank, row in enumerate(fts_results):
        rrf_scores[row["rowid"]] = rrf_scores.get(row["rowid"], 0) + 1 / (RRF_K + rank + 1)

    for rank, row in enumerate(vec_results):
        rrf_scores[row["rowid"]] = rrf_scores.get(row["rowid"], 0) + 1 / (RRF_K + rank + 1)

    top_ids = sorted(rrf_scores, key=lambda r: rrf_scores[r], reverse=True)[:k]

    results = []
    for rowid in top_ids:
        meta = conn.execute(
            "SELECT content, source FROM vec_meta WHERE rowid = ?", (rowid,)
        ).fetchone()
        if meta:
            results.append(dict(meta))

    return results
```

### memory/extractor.py — auto-extract profile facts

```python
import re
import sqlite3
from memory.store import upsert_profile

# Patterns that signal a learnable fact about the user
FACT_PATTERNS = [
    (r"\bmy name is (\w+)", "name"),
    (r"\bi(?:'m| am) (?:a |an )?(.+?)(?:\.|,|$)", "role"),
    (r"\bi (?:work|study) (?:at|in|on) (.+?)(?:\.|,|$)", "context"),
    (r"\bmy (.+?) is (.+?)(?:\.|,|$)", None),   # generic "my X is Y"
]

def extract_and_store(conn: sqlite3.Connection, user_text: str):
    """
    Run after each user turn. Extract facts and upsert into user_profile.
    Lightweight regex — no LLM call needed.
    """
    text = user_text.lower().strip()

    for pattern, key in FACT_PATTERNS:
        m = re.search(pattern, text)
        if not m:
            continue

        if key:
            upsert_profile(conn, key, m.group(1).strip(), confidence=0.8)
        else:
            # Generic "my X is Y"
            if len(m.groups()) >= 2:
                upsert_profile(conn, m.group(1).strip(), m.group(2).strip(), confidence=0.7)
```

### core/context.py

```python
import sqlite3
from memory.store import get_recent_turns, get_user_profile
from memory.retrieval import hybrid_search, should_retrieve
from config import CONTEXT_PROFILE, CONTEXT_RECENT, CONTEXT_RETRIEVED

async def build_context(conn: sqlite3.Connection, query: str, session_id: str) -> str:
    parts = []

    # Tier 1: User profile (always)
    profile = get_user_profile(conn)
    if profile:
        profile_text = "\n".join(f"{k}: {v}" for k, v in profile.items())
        parts.append(f"USER PROFILE:\n{profile_text}")

    # Tier 2: Recent turns (always)
    recent = get_recent_turns(conn, session_id, max_tokens=CONTEXT_RECENT)
    if recent:
        parts.append(f"RECENT CONVERSATION:\n{recent}")

    # Tier 3: Semantic retrieval (only when needed)
    if should_retrieve(query):
        results = await hybrid_search(conn, query, k=5)
        if results:
            retrieved = "\n---\n".join(r["content"] for r in results)
            parts.append(f"RELEVANT MEMORY:\n{retrieved}")

    return "\n\n".join(parts)
```

### memory/indexer.py

```python
import os
import sqlite3
from pathlib import Path
from config import HOME

INDEXED_EXTENSIONS = {
    ".pdf", ".pptx", ".ppt", ".docx", ".doc",
    ".txt", ".md", ".csv", ".py", ".ipynb", ".json"
}

def scan_home(conn: sqlite3.Connection, verbose: bool = False):
    """Incremental scan — only processes files changed since last index."""
    for root, dirs, files in os.walk(HOME):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            path = Path(root) / filename
            if path.suffix.lower() not in INDEXED_EXTENSIONS:
                continue
            _index_file(conn, path, verbose)
    conn.commit()

def _index_file(conn: sqlite3.Connection, path: Path, verbose: bool):
    try:
        stat   = path.stat()
        mtime  = str(stat.st_mtime)

        existing = conn.execute(
            "SELECT modified_at FROM files WHERE path = ?", (str(path),)
        ).fetchone()
        if existing and existing["modified_at"] == mtime:
            return

        tags = _infer_tags(path)
        conn.execute(
            """INSERT OR REPLACE INTO files
               (path, name, extension, size_kb, modified_at, tags)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (str(path), path.name, path.suffix.lower(),
             stat.st_size // 1024, mtime, tags)
        )
        if verbose:
            print(f"  indexed: {path.name}")

    except (PermissionError, OSError):
        pass

def _infer_tags(path: Path) -> str:
    parts      = [p.lower() for p in path.parts]
    name_parts = path.stem.lower().replace("_", " ").replace("-", " ").split()
    return ",".join(dict.fromkeys(parts + name_parts))
```

### Wire everything into main.py

Add at the top of `main.py`:

```python
from memory.db import get_connection
from memory.store import save_turn, log_operation
from memory.extractor import extract_and_store
from core.context import build_context

conn = get_connection()
```

Update `run_once()`:

```python
async def run_once(query: str):
    global agent, current_model

    model = select_model(query)
    if model != current_model:
        current_model = model
        agent = build_agent(current_model, think=think_mode)

    print_user(query)

    # Save user turn + extract any profile facts
    save_turn(conn, session_id, "user", query)
    extract_and_store(conn, query)

    # Build context from memory
    context = await build_context(conn, query, session_id)

    # Run agent
    response = await run_with_streaming(agent, query, context=context)

    # Save assistant turn
    save_turn(conn, session_id, "assistant", response)

    print_separator()
```

Wire `log_operation` into `tools/files.py` `_log_operation`:

```python
def _log_operation(op: str, src: str, dst: str):
    from main import conn
    from memory.store import log_operation
    log_operation(conn, op, src, dst)
```

Add `--init` flag in `main()`:

```python
if "--init" in sys.argv:
    from memory.db import get_connection
    from memory.indexer import scan_home
    console.print("[accent]Building file index...[/accent]")
    scan_home(get_connection(), verbose=True)
    console.print("[success]Done.[/success]")
    return
```

**Pass condition:** Ask two questions in sequence → second answer references first. `orion find my signals notes` → returns actual files. `orion --init` → scans and indexes home directory.

---

## Stage 5 — Web + Media Tools

**Goal:** DuckDuckGo search, page extraction, YouTube/media search all working.

### Stage 5 dependencies

```bash
uv add ddgs trafilatura playwright
uv run playwright install webkit
```

### tools/search.py

```python
from ddgs import DDGS

async def web_search(query: str, max_results: int = 5) -> str:
    """Search the web via DuckDuckGo. Returns title + URL + snippet per result."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return f"No results for: {query}"
        lines = []
        for r in results:
            lines.append(f"**{r['title']}**\n{r['href']}\n{r['body']}\n")
        return "\n".join(lines)
    except Exception as e:
        return f"Search failed: {e}"
```

### tools/browser.py

```python
import subprocess
import httpx
import trafilatura
from pathlib import Path
from safety.boundaries import validate_path

async def open_url(url: str) -> str:
    """Open a URL or local file in the default browser/app."""
    if url.startswith(("http://", "https://")):
        if not _is_online():
            return "Offline: cannot open web URLs right now."
        subprocess.Popen(["xdg-open", url])
        return f"Opened: {url}"
    else:
        ok, resolved = validate_path(url)
        if not ok:
            return resolved
        if not Path(resolved).exists():
            return f"File not found: {url}"
        subprocess.Popen(["xdg-open", resolved])
        return f"Opened: {Path(resolved).name}"

async def fetch_page(url: str) -> str:
    """
    Extract clean text from a web page.
    Tier 1: Trafilatura (fast, no browser, works for ~80% of pages).
    Tier 2: Playwright WebKit (JS-heavy pages, launched and killed immediately).
    """
    if not _is_online():
        return "Offline: cannot fetch web pages right now."

    # Tier 1
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            r    = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
            html = r.text
        text = trafilatura.extract(html, include_links=False,
                                   include_images=False, output_format="markdown")
        if text and len(text) > 200:
            return text[:6000]
    except Exception:
        pass

    # Tier 2
    return await _playwright_extract(url)

async def _playwright_extract(url: str) -> str:
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.webkit.launch(headless=True)
            page    = await browser.new_page()
            await page.goto(url, timeout=15000)
            content = await page.content()
            await browser.close()
        text = trafilatura.extract(content, output_format="markdown")
        return text[:6000] if text else "Could not extract content."
    except Exception as e:
        return f"Could not fetch page: {e}"

def _is_online() -> bool:
    import socket
    try:
        socket.setdefaulttimeout(2)
        socket.create_connection(("8.8.8.8", 53))
        return True
    except OSError:
        return False
```

### tools/search.py (add raw variant)

Add `web_search_raw` alongside `web_search` so other tools can read result objects directly without parsing formatted text:

```python
async def web_search_raw(query: str, max_results: int = 5) -> list[dict]:
    """Return raw DDGS result dicts: {title, href, body}."""
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except Exception:
        return []
```

### tools/media.py — YouTube + media search

```python
import subprocess
from tools.search import web_search_raw
from tools.browser import _is_online

SITE_FILTERS = {
    "youtube":    "site:youtube.com",
    "spotify":    "site:open.spotify.com",
    "soundcloud": "site:soundcloud.com",
}

async def open_media(query: str, site: str = "youtube") -> str:
    """
    Find and open media content.
    Examples: "latest markiplier video", "lofi hip hop playlist"
    Reads href directly from DDGS result objects — no regex on formatted text.
    """
    if not _is_online():
        return "Offline: cannot search for media right now."

    site_filter  = SITE_FILTERS.get(site, f"site:{site}")
    search_query = f"{query} {site_filter}"
    results      = await web_search_raw(search_query, max_results=5)

    if not results:
        return f"No results found for: {query}"

    # Prefer direct watch URLs over channel or homepage URLs
    def is_watch_url(href: str) -> bool:
        return "youtube.com/watch" in href or "youtu.be/" in href

    watch = next((r["href"] for r in results if is_watch_url(r["href"])), None)
    url   = watch or results[0]["href"]

    subprocess.Popen(["xdg-open", url])
    title = next((r["title"] for r in results if r["href"] == url), url)
    return f"Opening: {title}\n{url}"
```

**Pass condition:** `orion search for signals and systems lecture notes` → DuckDuckGo results appear. `orion open the latest markiplier video` → YouTube video opens in browser.

---

## Stage 6 — Safety Layer

**Goal:** All safety checks locked in before real-world use.

### safety/confirm.py

```python
from prompt_toolkit import prompt
from prompt_toolkit.formatted_text import HTML

DESTRUCTIVE_KEYWORDS = [
    "delete", "remove", "trash", "wipe", "clear",
    "overwrite", "replace", "format"
]

def requires_confirmation(action: str) -> bool:
    return any(k in action.lower() for k in DESTRUCTIVE_KEYWORDS)

async def ask_confirmation(description: str) -> bool:
    from ui.renderer import console
    console.print()
    console.print(f"[warning]⚠  {description}[/warning]")
    console.print("[dim]Type yes to confirm, anything else to cancel[/dim]")
    answer = await prompt(HTML('<ansiblue>  ❯ </ansiblue>'), async_=True)
    return answer.strip().lower() in ("yes", "y")
```

Wire into `tools/files.py` — before `delete` and `overwrite` actions:

```python
if action == "delete":
    ok, resolved = validate_path(path)
    if not ok:
        return resolved
    from safety.confirm import ask_confirmation
    confirmed = await ask_confirmation(f"Move to trash: {Path(resolved).name}?")
    if not confirmed:
        return "Cancelled."
    subprocess.run(["gio", "trash", resolved])
    _log_operation("delete", resolved, "trash")
    return f"Moved to trash: {Path(resolved).name}"
```

**Pass condition:** `orion delete test.txt` → shows confirmation. Only deletes after "yes". `orion move test.txt to /etc/` → blocked with clear message.

---

## Stage 7 — Polish + UX Details

**Goal:** Slash commands, undo, session history, model switching, pipe support all complete.

### Slash commands — wire into main.py

```python
import sys
import os
import shutil as _shutil
from pathlib import Path

async def handle_slash(user_input: str):
    global agent, current_model, think_mode

    cmd  = user_input.split()[0].lower()
    args = user_input[len(cmd):].strip()

    if cmd == "/help":
        console.print("""
[accent]orion slash commands[/accent]

  [dim]/think[/dim]    force chain-of-thought reasoning
  [dim]/fast[/dim]     switch to qwen3-4b (quick tasks)
  [dim]/slow[/dim]     switch to qwen3-8b (reasoning tasks)
  [dim]/clear[/dim]    clear the terminal
  [dim]/undo[/dim]     undo last file operation
  [dim]/history[/dim]  show this session's conversation
  [dim]/memory[/dim]   show what orion knows about you
  [dim]/scan[/dim]     re-index your home directory
  [dim]/exit[/dim]     quit
""")

    elif cmd == "/think":
        think_mode = True
        agent = build_agent(current_model, think=True)
        console.print("[success]Chain-of-thought enabled.[/success]")

    elif cmd == "/fast":
        from config import MODEL_FAST
        current_model = MODEL_FAST
        agent = build_agent(current_model, think=think_mode)
        console.print(f"[success]Switched to {MODEL_FAST}[/success]")

    elif cmd == "/slow":
        from config import MODEL_PRIMARY
        current_model = MODEL_PRIMARY
        agent = build_agent(current_model, think=think_mode)
        console.print(f"[success]Switched to {MODEL_PRIMARY}[/success]")

    elif cmd == "/clear":
        console.clear()

    elif cmd == "/undo":
        await undo_last_operation()

    elif cmd == "/history":
        show_history()

    elif cmd == "/memory":
        show_memory()

    elif cmd == "/scan":
        from memory.indexer import scan_home
        console.print("[dim]Scanning file system...[/dim]")
        scan_home(conn, verbose=False)
        console.print("[success]File index updated.[/success]")

    elif cmd in ("/exit", "/quit"):
        sys.exit(0)

    else:
        console.print(f"[error]Unknown command: {cmd}[/error]")
        console.print("[dim]Type /help for available commands.[/dim]")


async def undo_last_operation():
    from memory.store import get_last_operation
    last = get_last_operation(conn)
    if not last:
        console.print("[dim]Nothing to undo.[/dim]")
        return
    if last["operation"] == "move":
        _shutil.move(last["destination"], last["source"])
        console.print(f"[success]Undone: moved back to {last['source']}[/success]")
    elif last["operation"] == "rename":
        os.rename(last["destination"], last["source"])
        console.print(f"[success]Undone: renamed back to {Path(last['source']).name}[/success]")
    elif last["operation"] == "delete":
        console.print("[dim]Deletion sent to trash — restore via file manager.[/dim]")


def show_history():
    from memory.store import get_recent_turns
    history = get_recent_turns(conn, session_id, max_tokens=4000)
    if history:
        console.print(history)
    else:
        console.print("[dim]No history yet.[/dim]")


def show_memory():
    from memory.store import get_user_profile
    profile = get_user_profile(conn)
    if profile:
        for k, v in profile.items():
            console.print(f"  [accent]{k}[/accent]  [dim]{v}[/dim]")
    else:
        console.print("[dim]Nothing stored yet.[/dim]")
```

**Pass condition:** All slash commands respond correctly. `/undo` reverses last move/rename. `/memory` shows extracted profile facts. `/think` enables CoT on next query.

---

## Installation

```bash
# System packages
sudo apt install ffmpeg gio-utils

# Install uv (if not already present)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Project setup — run once inside the project directory
cd ~/Programming/Projects/cli-assistant
uv init --python 3.13        # creates pyproject.toml + .venv
uv add rich prompt_toolkit pydantic-ai openai httpx sqlite-vec
uv add ddgs trafilatura playwright psutil
uv run playwright install webkit

# Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:4b
ollama pull nomic-embed-text

# First run — build file index
uv run main.py --init

# Normal start
uv run main.py
```

### Shell command

```bash
cat > ~/.local/bin/orion << 'EOF'
#!/bin/bash
exec uv run --directory ~/Programming/Projects/cli-assistant python main.py "$@"
EOF
chmod +x ~/.local/bin/orion
```

Now: `orion open the latest markiplier video`

### Optional — user config

```toml
# ~/.orion/config.toml
model_primary = "qwen3:4b"
model_fast    = "qwen3:4b"
theme         = "mocha"
max_width     = 100
```

---

## What Each Stage Unlocks

| Stage | What you can do |
| ----- | --------------- |
| 1 | Confirm Ollama + Qwen3 work, streaming to terminal |
| 2 | Full visual interface — Catppuccin theme, spinner, startup. Model pre-warmed. |
| 3 | Real agent, natural language invocation, file ops, shell, tool activity in spinner |
| 4 | Persistent memory, "find my signals notes" works, conversation history |
| 5 | Web search, page extraction, `orion open the latest markiplier video` |
| 6 | Safe for real files — delete protection, path sandboxing |
| 7 | Slash commands, undo, `/think` mode, daily-driver ready |
