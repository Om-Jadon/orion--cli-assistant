# Orion CLI Assistant — Code Walkthrough

This document is a file-by-file guide to understanding the Orion codebase in the best possible reading order. Start from the top and work downward. Each section explains what a file does, why it exists, and highlights any non-obvious patterns.

---

## Table of Contents

1. [Reading Order at a Glance](#reading-order-at-a-glance)
2. [Architecture Map](#architecture-map)
3. [Layer 0 — Project Setup](#layer-0--project-setup)
   - [pyproject.toml](#pyprojecttoml)
   - [src/orion/config.py](#configpy)
4. [Layer 1 — Application Entry](#layer-1--application-entry)
   - [src/orion/main.py](#mainpy)
5. [Layer 2 — UI Primitives](#layer-2--ui-primitives)
   - [src/orion/ui/renderer.py](#uirendererpy)
   - [src/orion/ui/spinner.py](#uispinnerpy)
   - [src/orion/ui/input.py](#uiinputpy)
   - [src/orion/ui/startup.py](#uistartuppy)
   - [src/orion/ui/slash.py](#uislashpy)
   - [src/orion/ui/onboarding.py](#uionboardingpy)
6. [Layer 3 — Safety](#layer-3--safety)
   - [src/orion/safety/boundaries.py](#safetyboundariespy)
   - [src/orion/safety/confirm.py](#safetyconfirmpy)
7. [Layer 4 — Memory Subsystem](#layer-4--memory-subsystem)
   - [src/orion/memory/db.py](#memorydbpy)
   - [src/orion/memory/embeddings.py](#memoryembeddingspy)
   - [src/orion/memory/store.py](#memorystorepy)
   - [src/orion/memory/indexer.py](#memoryindexerpy)
   - [src/orion/memory/retrieval.py](#memoryretrievalpy)
8. [Layer 5 — Tools](#layer-5--tools)
   - [src/orion/tools/files.py](#toolsfilespy)
   - [src/orion/tools/memory_tool.py](#toolsmemory_toolpy)
   - [src/orion/tools/shell.py](#toolsshellpy)
   - [src/orion/tools/browser.py](#toolsbrowserpy)
   - [src/orion/tools/search.py](#toolssearchpy)
   - [src/orion/tools/media.py](#toolsmediapy)
9. [Layer 6 — Agent Core](#layer-6--agent-core)
   - [src/orion/core/trace_logging.py](#coretrace_loggingpy)
   - [src/orion/core/model_fallback.py](#coremodel_fallbackpy)
   - [src/orion/core/context.py](#corecontextpy)
   - [src/orion/core/agent.py](#coreagentpy)
   - [src/orion/core/streaming.py](#corestreamingpy)

**Self-Knowledge Injection:**
The system prompt for the agent is dynamically hydrated with its own environment state, including the explicit path to its configuration file:
`- Config: {config.CONFIG_FILE}`
This ensures Orion can accurately answer user questions about where its settings are located without hallucinating standard paths.
10. [Data Flow: A Full Turn](#data-flow-a-full-turn)
11. [Key Design Patterns](#key-design-patterns)

---

## Reading Order at a Glance

```
pyproject.toml          → understand deps and constraints
src/orion/config.py       → understand all runtime constants
src/orion/main.py         → understand how the process boots and routes modes

src/orion/ui/renderer.py  → console & streaming output primitives
src/orion/ui/spinner.py   → async spinner (used during LLM wait)
src/orion/ui/input.py     → prompt_toolkit session setup
src/orion/ui/startup.py   → startup screen and preflight checks
src/orion/ui/slash.py     → runtime state + slash command handlers

safety/boundaries.py    → path validation, sudo blocking
safety/confirm.py       → interactive confirmation prompts + denial memory

memory/db.py            → SQLite setup, WAL mode, sqlite-vec, schema
memory/embeddings.py    → fastembed vector generation (lazy singleton)
memory/store.py         → read/write conversations, profile, operation log
memory/indexer.py       → incremental HOME directory file scan
memory/retrieval.py     → hybrid FTS + vector search with RRF fusion

tools/files.py          → file operations (find, read, open, move, delete)
tools/memory_tool.py    → manage_user_memory (unified add/update/delete)
tools/shell.py          → shell execution with safety checks
tools/browser.py        → open URLs, two-tier web page extraction
tools/search.py         → DuckDuckGo web search
tools/media.py          → media search + xdg-open launcher

core/trace_logging.py   → JSONL trace log writer (thread-safe, context-var scoped)
core/model_fallback.py  → Groq fallback model list
core/context.py         → three-tier context block assembly
core/agent.py           → PydanticAI agent construction + tool registration
core/streaming.py       → streaming runner, retry logic, Groq token fallback
```

---

## Architecture Map

```
┌─────────────────────────────────────────────────────────────────┐
│  main.py  (boots, routes: one-shot / pipe / interactive REPL)   │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
         ui/ layer     core/ layer    memory/ layer
        ─────────────  ────────────   ─────────────
        renderer.py    agent.py       db.py
        spinner.py     streaming.py   store.py
        input.py       context.py     retrieval.py
        startup.py     trace_log.py   embeddings.py
        slash.py       fallback.py    indexer.py
              │              │              │
              ▼              ▼              ▼
         tools/ layer   safety/ layer  memory/ layer
        ──────────────  ─────────────  ─────────────
        files.py        boundaries.py  db.py
        memory_tool.py  confirm.py     store.py
        shell.py                       retrieval.py
        browser.py                     embeddings.py
        search.py                      indexer.py
        media.py
```

Dependencies flow **downward only** — tools and memory never import from `core/` or `ui/`, keeping the layers cleanly separated.

---

## Layer 0 — Project Setup

### `pyproject.toml`

The project uses [uv](https://github.com/astral-sh/uv) as its package manager with `pyproject.toml` as the single source of truth.

**Key dependencies and why they exist:**

| Package | Role |
|---|---|
| `pydantic-ai` | Agent orchestration, tool-calling abstraction over cloud LLM APIs |
| `rich` | Terminal rendering: markdown streaming, themed output, spinners |
| `prompt-toolkit` | Interactive REPL input, file history, keybindings, confirmation prompts |
| `sqlite-vec` | Adds a SQLite extension for vector similarity search (ANN over float arrays) |
| `fastembed` | Runs local BAAI/bge-small-en-v1.5 embeddings — no Ollama required |
| `ddgs` | DuckDuckGo search API client |
| `trafilatura` | Fast HTML-to-text article extractor |
| `playwright` | JS-rendered page fallback when trafilatura yields nothing |
| `httpx` | Used for connectivity checks in the startup screen |
| `openai` | Required as peer dep by pydantic-ai for the OpenAI provider |

**Test config:**
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"   # all async tests run automatically without @pytest.mark.asyncio
pythonpath   = ["."]    # imports resolve from project root, e.g. `from config import ...`
```

---

### `src/orion/config.py`

**The configuration hub** — every constant that configures runtime behavior lives here. `config.py` is imported by almost every module, so reading it first establishes the vocabulary of the system.

**Important patterns:**

**1. Idempotent module reload protection**

```python
_mod = sys.modules.get(__name__)
CONFIG_FILE = (
    _mod.CONFIG_FILE
    if _mod is not None and hasattr(_mod, "CONFIG_FILE")
    else ORION_DIR / "config.toml"
)
```

Tests override `CONFIG_FILE` before importing `config`. This guard ensures that when the module is re-imported (e.g. via `importlib.reload`), the test-injected path is preserved rather than reset to the default. Without this, test isolation would break.

**2. Provider detection by string prefix**

```python
def _detect_provider(model_string: str) -> str:
    if model_string.startswith("openai:"): return "openai"
    if model_string.startswith("anthropic:"): return "anthropic"
    if model_string.startswith("gemini-"): return "gemini"
    ...
```

The `model_string` format (`provider:model-name`) is how pydantic-ai identifies which API client to use. Orion parses the prefix to know which API key env var to validate at startup.

**3. Absolute Resilience: Safe Type Casting**

```python
def _as_int(value, default: int) -> int:
    try:
        if isinstance(value, (int, float)): return int(value)
        if isinstance(value, str): return int(value.strip())
        return default
    except (ValueError, TypeError):
        return default
```

Orion implements "Absolute Resilience" for its configuration. Even if a user manually sabotages `config.toml` with invalid types (e.g. `max_width = "infinity"`), the parser catches the error and falls back to safe factory defaults instead of crashing.

**4. Fail-fast on missing model**

```python
MODEL_STRING: str = _require_model_string(_user.get("model_string"))
```

If `model_string` is absent from `~/.orion/config.toml`, Orion exits immediately with a clear error message. This prevents cryptic failures downstream.

**4. Context budget constants**

```python
CONTEXT_PROFILE   = 800    # max chars of user profile injected per turn
CONTEXT_RECENT    = 2000   # max chars of recent conversation history
CONTEXT_RETRIEVED = 2000   # max chars from semantic retrieval results
CONTEXT_RESERVE   = 3000   # headroom reserved for LLM's own response
```

These bound the context window injection and prevent accidentally sending a 50-turn conversation history that overflows the model's limit.

---

## Layer 1 — Application Entry

### `src/orion/main.py`

`main.py` is the process entry point. It handles **three distinct operating modes**, wires up the global singletons, and manages the interactive REPL loop.

**Module-level initialization (runs on import):**

```python
ORION_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.DEBUG, filename=str(ORION_DIR / "debug.log"))
trace_logging.initialize()

state = slash.RuntimeState(agent=build_agent(), session_id=str(uuid.uuid4()))
trace_logging.set_session_id(state.session_id)
refresh_console_settings()    # Force UI theme/width refresh on startup
conn = get_connection()
file_tools.set_connection(conn)
```

This runs at import time (before `main()` is called). The agent, DB connection, and session ID are created once and shared across all turns. `file_tools.set_connection(conn)` injects the shared DB connection into `tools/files.py` so file operations can log to the operation log (enabling `/undo`).

**Three routing modes inside `async def main()`:**

```
sys.argv > 1 and stdin is a tty  →  one-shot mode    (run_once, then exit)
stdin is NOT a tty               →  pipe mode         (read all stdin, run_once, then exit)
otherwise                        →  interactive REPL  (loop)
```

**Pipe mode detail:**

```python
piped_input = sys.stdin.read()
user_query  = sys.argv[1] if len(sys.argv) > 1 else "Analyze this:"
full_query  = f"{user_query}\n\n```\n{piped_input[:4000]}\n```"
```

The piped content is capped at 4000 chars and fenced in a markdown code block before being sent to the agent. The user's query (e.g. `"what went wrong?"`) becomes the instruction prefix.

**Background tasks in interactive mode:**

```python
scan_task    = asyncio.create_task(asyncio.to_thread(_run_background_scan))
cleanup_task = asyncio.create_task(asyncio.to_thread(_run_log_retention_cleanup))
```

Both `_run_background_scan` (indexes your HOME directory) and `_run_log_retention_cleanup` (deletes old trace logs) run in background threads so they don't block the REPL. 

**Database Concurrency Safety:**
To prevent "Database is locked" errors during background indexing, Orion implements **Thread-Local Isolation**. The background task creates its own dedicated SQLite connection instead of sharing the main thread's connection.

**The `run_once` function** handles a complete single turn:

```
1. start_turn(...)     — opens a trace log entry
2. reset_turn_state()  — clears the denial memory in safety/confirm.py
3. save_turn(...)      — persists user message to SQLite
4. build_context(...)  — assembles the 3-tier context string
5. run_with_streaming(...) — calls the agent, streams response to terminal
6. save_turn(...)      — persists assistant response
7. end_turn(...)       — closes the trace log entry
```

---

## Layer 2 — UI Primitives

### `src/orion/ui/renderer.py`

Defines the **global `console` object** and all terminal rendering helpers. Every other module that prints to screen imports `console` from here.

**Theme system:**

```python
MOCHA = Theme({
    "user":      "bold #CDD6F4",
    "assistant": "#89DCEB",
    "success":   "#A6E3A1",
    "warning":   "#F9E2AF",
    "error":     "#F38BA8",
    "accent":    "#89B4FA",
    ...
})
console = Console(theme=MOCHA, highlight=False, width=MAX_WIDTH)
```

All colours are from the [Catppuccin](https://github.com/catppuccin/catppuccin) palette. Orion dynamically supports **Mocha** (Dark) and **Latte** (Light) modes via `config.THEME`. The `refresh_console_settings()` function uses `console.push_theme()` to live-inject these style overrides into the global Rich console.

**Live streaming with `Rich.Live`:**

```python
async def stream_response(token_gen) -> str:
    content = ""
    with Live(Panel(Markdown(""), ...), refresh_per_second=15) as live:
        async for token in token_gen:
            content += token
            live.update(Panel(Markdown(content), ...))
    return content
```

`Rich.Live` re-renders a panel in-place on each update. As each token arrives, the Markdown is re-parsed and the panel redrawn — giving the appearance of live typewriter output with proper markdown formatting rendered incrementally.

---

### `src/orion/ui/spinner.py`

An **asyncio-native spinner** built without threads — avoids race conditions with the event loop.

```python
def start(self, label: str = "thinking"):
    self._task = asyncio.create_task(self._spin())

async def _spin(self):
    for frame in itertools.cycle(BRAILLE):
        sys.stdout.write(f"\r{ORION_COLOR}◆{RESET}  {THINKING_COLOR}{frame} {self._label}{RESET}")
        await asyncio.sleep(0.08)
```

The spinner creates an asyncio Task that loops through braille frames at 12.5 fps. `\r` (carriage return, no newline) overwrites the same terminal line on each tick. The module keeps a global `_ACTIVE_SPINNER` reference so `stop_active_spinner()` can halt it from anywhere (such as from `safety/confirm.py` before displaying a confirmation prompt).

---

### `src/orion/ui/input.py`

Builds the **prompt_toolkit session** for the interactive REPL.

```python
return PromptSession(
    history=FileHistory(str(HISTORY_FILE)),
    auto_suggest=AutoSuggestFromHistory(),
    key_bindings=bindings,
    enable_open_in_editor=True,
)
```

- **`FileHistory`**: persists command history to `~/.orion/history` across sessions (like bash history).
- **`AutoSuggestFromHistory`**: shows greyed-out completions as you type.
- **`enable_open_in_editor`**: pressing `Ctrl+X Ctrl+E` opens `$EDITOR` for multi-line input.
- **Custom keybindings**: `Ctrl+L` clears the screen; `Ctrl+C` raises `KeyboardInterrupt` cleanly.

---

### `src/orion/ui/startup.py`

Shows the **startup screen** and runs preflight checks before entering the REPL.

```python
checks = [
    (PROVIDER,   api_ok,   "ready" if api_ok else "missing"),
    ("memory",   db_ok,    "active" if db_ok else "run /scan"),
    ("index",    index_ok, f"{_index_count():,} files" if index_ok else "run /scan"),
]
```

Three checks run at startup:
1. **API key check**: verifies the required env var (e.g. `OPENAI_API_KEY`) is set. If missing, it prints a clear error to stderr and calls `sys.exit(1)` before any UI renders.
2. **DB check**: tests if `~/.orion/memory.db` exists.
3. **Index check**: counts indexed files in the `files` table — a zero count tells the user to run `/scan`.

---

### `src/orion/ui/slash.py`

The **slash command router** and **session state container**.

**`RuntimeState` dataclass:**

```python
@dataclass
class RuntimeState:
    agent: Any
    session_id: str
```

This is the only mutable session-level state. It's created once in `main.py` and passed by reference to `handle_slash`. The agent can be swapped at runtime (though this is not currently exposed via UI).

**Available slash commands** and what they do internally:

| Command | Behaviour |
|---|---|
| `/help` | Prints command list |
| `/clear` | `console.clear()` |
| `/undo` | Reads `operation_log`, reverses `move`/`rename`/`delete`/`create` via stack |
| `/reset` | Clears current session history turns from database |
| `/history` | Calls `get_recent_turns()`, prints to console |
| `/memory` | Calls `get_user_profile()`, prints key-value pairs |
| `/config` | Opens `config.toml` in system editor via `xdg-open` |
| `/scan` | Runs `scan_home()` in a thread via `asyncio.to_thread` |
| `/exit`, `/quit` | `raise SystemExit(0)` |

**`/undo` internals:**

Undo maintains a stack in the `operation_log` table. It supports reversing:
- **Moves/Renames**: Swaps source and destination back.
- **Deletions**: Uses `gio trash --restore` to pull files back from the system trash.
- **Creations**: Moves newly created files (via `write_file`) into the trash.

Successful undos inject a `[UNDO NOTICE]` into the conversation history so the AI is aware the filesystem state has reverted.

---

### `src/orion/ui/onboarding.py`

Handles the **Stage 8: Production Onboarding** flow. This module is active only on first launch or if the configuration is deleted.

**Key Features:**
- **Step-by-Step Wizard**: Guides user through identity, AI provider, and authentication.
- **Dynamic Connection Testing**: Verifies the API key against the cloud provider *before* finishing setup.
- **Persistence**: Generates a self-documenting `config.toml` with professional comments on and success.
- **Error Resilence**: Includes a persistent authentication loop that requires a valid key to proceed.

---

## Layer 3 — Safety

### `src/orion/safety/boundaries.py`

Two pure functions that operate as the **security boundary** of the system.

**`validate_path(path)`:**

```python
resolved = Path(path).expanduser().resolve()
resolved.relative_to(HOME)   # raises ValueError if outside HOME
return True, str(resolved)
```

`Path.resolve()` follows symlinks and normalises `..` components — it cannot be fooled by path-traversal attacks like `~/../../etc/passwd`. `relative_to(HOME)` raises `ValueError` if the resolved path is outside HOME entirely. This check wraps every file tool operation.

**`validate_sudo(command)`:**

```python
BLOCKED_COMMANDS = ["sudo", "su", "pkexec", "doas"]
DANGER_PATTERNS  = ["rm -rf", "rm -r /", "chmod -R 777", "dd if=", "> /dev/", ...]

tokens = shlex.split(command)
for blocked in BLOCKED_COMMANDS:
    if blocked in tokens:    # checks token-level, not substring
        return True, "sudo/root commands are not permitted."
```

Uses `shlex.split` to tokenise before checking — so `echo "sudo"` wouldn't match (it's the second token not the first), but `sudo apt` would. Checks are done on the token list to avoid substring false-positives.

---

### `src/orion/safety/confirm.py`

The **interactive confirmation system** with per-turn denial memory — the most complex file in the safety layer.

**`ConfirmationResult` dataclass:**

```python
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
```

The result object is fully immutable (`frozen=True`) and its `.confirmed` property allows callers to write `if not confirmed.confirmed:` naturally. The `repeated_denial` flag signals to the caller (and the agent via the returned string) that this exact action was already denied in this turn.

**Denial memory mechanism:**

```python
_denied_action_keys: set[str] = set()

def _make_action_key(scope, action, source_path, destination_path, command) -> str:
    return "|".join([scope, action, source_path or "", destination_path or "", command or ""])
```

When a user denies an action, its canonical key is stored in `_denied_action_keys`. If the **same action on the same targets** is attempted again in the same turn (which can happen if the LLM retries a denied tool call), it gets an instant `repeated_denial=True` response without re-prompting.

`reset_turn_state()` is called at the start of every turn in `main.py` to clear the set.

**Why this is important:** Without denial memory, a confused LLM could loop — call the same destructive tool repeatedly after the user said "no", pestering the user with multiple prompts for the same action.

---

## Layer 4 — Memory Subsystem

### `src/orion/memory/db.py`

Opens and configures the **SQLite connection** with extensions and schema.

```python
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row   # rows as dict-like, access by column name
conn.enable_load_extension(True)
sqlite_vec.load(conn)             # load vector extension
conn.enable_load_extension(False) # re-lock extension loading
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
```

- **`check_same_thread=False`**: needed because the connection is created on the main thread but accessed from background threads (scan task). SQLite in WAL mode supports concurrent reads, making this safe.
- **WAL mode**: Write-Ahead Logging decouples reads from writes — the background scan can write while the main thread reads, without blocking.
- **`sqlite_vec`**: a C extension loaded at runtime that adds a `vec0` virtual table type for approximate nearest-neighbor vector search.

**Schema (7 tables):**

| Table | Purpose |
|---|---|
| `conversations` | Every user/assistant turn, scoped by `session_id` |
| `user_profile` | Key-value facts about the user (name, role, context) with confidence |
| `files` | Indexed file metadata (path, name, ext, size, mtime, tags) |
| `operation_log` | Records file moves/deletes for `/undo` |
| `memory_fts` | FTS5 virtual table for full-text keyword search |
| `vec_memory` | sqlite-vec virtual table: stores float embeddings |
| `vec_meta` | Maps `vec_memory` rowids back to text content and source |

---

### `src/orion/memory/embeddings.py`

A thin wrapper around **fastembed** with a lazy-loaded singleton model.

```python
_model: TextEmbedding | None = None

def _get_model() -> TextEmbedding:
    global _model
    if _model is None:
        _model = TextEmbedding(EMBED_MODEL)   # loads BAAI/bge-small-en-v1.5
    return _model

async def embed(text: str) -> list[float]:
    model = _get_model()
    vector = await asyncio.to_thread(lambda: next(model.embed([text])))
    return vector[:EMBED_DIM].tolist()
```

- **Lazy singleton**: the model is only loaded when embedding is first needed (not on import). Loading a fastembed model downloads weights on first call — you don't want that at import time.
- **`asyncio.to_thread`**: fastembed's `embed()` is synchronous and CPU-bound. Offloading it to a thread avoids blocking the event loop while the ONNX inference runs.
- **`serialize(floats)`**: packs the float list into raw bytes using `struct.pack` — the format sqlite-vec expects for binary vector storage.

---

### `src/orion/memory/store.py`

**CRUD operations** for the SQLite schema — conversations, profiles, and operation logs.

**Token estimation for context windowing:**

```python
def _estimate_token_count(text: str) -> int:
    word_estimate = len(text.split())
    char_estimate = ceil(len(text) / 4)
    return max(word_estimate, char_estimate)
```

Takes the maximum of two estimates — word count (fast but underestimates code) and char count / 4 (the classic approximation for BPE tokenisers). Using `max` gives a conservative (larger) estimate, meaning the context budget is less likely to overflow.

**`get_recent_turns`** walks backwards through the last 20 messages, accumulating tokens until the budget is exceeded:

```python
rows fetched: DESC order (newest first)
iterated:     reversed (oldest first for display)
```

This means you get the most recent turns within budget, displayed oldest-first for natural reading order.

**Agentic Memory Flow**: Note that Fact Extraction has transitioned from a background regex process to an **Agentic Memory** model. The AI now intentionally chooses to remember or forget information using specialized tools.

**`upsert_profile`** uses SQLite's `INSERT OR REPLACE ... ON CONFLICT` to update existing profile keys atomically:

```python
conn.execute("""
    INSERT INTO user_profile (key, value, confidence)
    VALUES (?, ?, ?)
    ON CONFLICT(key) DO UPDATE SET
        value      = excluded.value,
        confidence = excluded.confidence,
        updated_at = datetime('now')
""", ...)
```

---

    (r"\bi (?:work|study) (?:at|in|on) (.+?)(?:\.|,|$)", "context"),
    (r"\bmy (.+?) is (.+?)(?:\.|,| and |$)",   None),  # generic: "my X is Y"
]
```

The generic pattern (`None` key) uses two capture groups: `my (key) is (value)` — so "my editor is neovim" extracts `{"editor": "neovim"}` without needing a specific rule for every possible fact.

Called after **every user turn** in `main.py` — fast because it's pure regex, no I/O.

---

### `src/orion/memory/indexer.py`

**Incremental home directory scanner** — builds the file metadata index used by `find_files`.

```python
def scan_home(conn, verbose=False):
    for root, dirs, files in os.walk(HOME):
        dirs[:] = [d for d in dirs if not d.startswith(".")]  # skip hidden dirs
        for filename in files:
            path = Path(root) / filename
            if path.suffix.lower() not in INDEXED_EXTENSIONS:
                continue
            _index_file(conn, path, verbose)
```

**Incremental (not full) scan:**

```python
existing = conn.execute("SELECT modified_at FROM files WHERE path = ?", (str(path),)).fetchone()
if existing and existing["modified_at"] == mtime:
    return   # file unchanged — skip
```

It compares the file's `st_mtime` (filesystem timestamp as a string) with the stored value. Only changed/new files are re-indexed, making re-scans fast.

**Tag inference:**

```python
def _infer_tags(path: Path) -> str:
    parts      = [p.lower() for p in path.parts]       # directory components
    name_parts = path.stem.lower().replace("_", " ").replace("-", " ").split()
    return ",".join(dict.fromkeys(parts + name_parts))  # deduplicated, insertion-ordered
```

Tags are a comma-separated string combining directory path components and filename tokens. This allows `find_files("notes")` to match a file at `~/Documents/project-notes.md` via the tag `"project notes"`.

**Indexed extensions:** `.pdf .pptx .ppt .docx .doc .txt .md .csv .py .ipynb .json`

---

### `src/orion/memory/retrieval.py`

The **hybrid retrieval engine** — combines full-text search (FTS5) and vector search (sqlite-vec) using Reciprocal Rank Fusion.

```python
async def hybrid_search(conn, query, k=5) -> list[dict]:
    # 1. BM25 keyword search
    fts_results = conn.execute(
        "SELECT rowid, content, bm25(memory_fts) as score FROM memory_fts WHERE memory_fts MATCH ? ORDER BY score ASC LIMIT 20",
        (_fts_escape(query),)
    ).fetchall()

    # 2. Vector similarity search
    query_vec = await embed(query)
    vec_results = conn.execute(
        "SELECT rowid, distance FROM vec_memory WHERE embedding MATCH ? ORDER BY distance LIMIT 20",
        (sqlite3.Binary(serialize(query_vec)),)
    ).fetchall()

    # 3. Reciprocal Rank Fusion
    rrf_scores: dict[int, float] = {}
    RRF_K = 60
    for rank, row in enumerate(fts_results):
        rrf_scores[row["rowid"]] += 1 / (RRF_K + rank + 1)
    for rank, row in enumerate(vec_results):
        rrf_scores[row["rowid"]] += 1 / (RRF_K + rank + 1)
```

**Why Reciprocal Rank Fusion (RRF)?**
- FTS5 returns BM25 scores (negative, more negative = better match) — not directly comparable to vector distances.
- RRF avoids score normalisation entirely. It only uses **rank position**: 1st place is worth `1/(60+1)`, 2nd is `1/(60+2)`, etc.
- Results appearing in both FTS and vector results get **double credit** — they are highly likely to be genuinely relevant.

**FTS escaping:**

```python
def _fts_escape(query: str) -> str:
    return '"' + query.replace('"', '""') + '"'
```

Wraps the query in double-quotes so FTS5 treats it as a phrase query rather than individual keyword tokens. Internal `"` are escaped by doubling. Without this, a query like `list files` would match any document with "list" OR "files" anywhere — much too broad.

**`MIN_RRF_SCORE = 0.01`**: Cuts out very weak matches. A result that only appears at rank 60 on one list scores `1/(60+60+1) ≈ 0.0082` — below threshold and filtered.

---

## Layer 5 — Tools

### `src/orion/tools/files.py`

The most **feature-dense tool file**, implementing six tools with safety, confirmations, and DB logging woven together.

**Connection injection:**

```python
_operation_conn = None
_search_conn    = None

def set_connection(conn):
    global _operation_conn, _search_conn
    _operation_conn = conn
    _search_conn    = conn
```

`main.py` calls `file_tools.set_connection(conn)` at startup. This avoids circular import issues (tools don't import from `main`) and gives the tools access to the shared SQLite connection for both search (via the `files` table) and operation logging (for `/undo`).

**Junk Folding and Filtering:**
To prevent "token-flood" scenarios, `files.py` maintains an `IGNORE_DIRS` set:
- `{".git", "node_modules", "__pycache__", ".venv", ".orion", ".pytest_cache"}`
All directory listings and recursive `find` calls dynamically filter any path containing these patterns, significantly reducing the AI's exploration cost.

**`find_files(query)` — two-tier search:**

```python
# Tier 1: SQLite index (fast, milliseconds)
rows = _search_conn.execute(
    "SELECT path FROM files WHERE name LIKE ? OR tags LIKE ? LIMIT 10",
    (f"%{query}%", f"%{query}%")
)

# Tier 2: `find` CLI fallback (slower, seconds)
out = await asyncio.to_thread(subprocess.run, ["find", str(HOME), "-maxdepth", "8", ...])
```

The index is consulted first; if it has results, the `find` subprocess is never spawned. The `find` call is wrapped in `asyncio.to_thread` so the blocking subprocess doesn't stall the event loop.

**`delete_file` — most defensively coded tool:**

```python
ok, resolved = validate_path(path)     # 1. boundary check
if not ok: return resolved
if not Path(resolved).exists():        # 2. existence check
    return f"Not found: {path}."
confirmed = await confirm.ask_file_action_confirmation("delete", ...)  # 3. confirmation
if not confirmed.confirmed: return "..."
await asyncio.to_thread(subprocess.run, ["gio", "trash", resolved])    # 4. async trash
_log_operation("delete", resolved, "trash")                            # 5. log for /undo
```

Using `gio trash` instead of `os.remove` means deleted files are recoverable from the system trash — a critical safety property.

**`_classify_move_action(src, dst)`:**

```python
if dst_path.exists() and dst_path.is_dir(): return "move"    # into an existing dir
if Path(src).parent == dst_path.parent:     return "rename"  # same dir, different name
return "move"
```

Distinguishes between a rename (same folder) and a move (different folder) to show the right description in the confirmation prompt.

### `src/orion/tools/memory_tool.py`

Implements **intentional memory management** — Orion chooses when to remember or forget information by calling this tool, rather than relying on brittle background extraction.

```python
async def manage_user_memory(action: Literal["upsert", "delete"], key: str, value: str = None) -> str:
    if action == "upsert":
        upsert_profile(conn, key, value, confidence=1.0)
    elif action == "delete":
        delete_profile_key(conn, key)
```

This tool is the exclusive method for profile state changes. The AI is instructed that if it does not call this tool, the fact is not saved.

---

### `src/orion/tools/shell.py`

Implements `run_shell` with a **deep destructive command classifier** before any execution.

**Command parsing pipeline:**

```
command string
    → _tokenize_shell()       (shlex with punctuation_chars)
    → _split_shell_commands() (split on &&, ||, ;, |, &)
    → per-segment analysis    (binary detection, flag analysis)
```

Using `shlex.shlex` with `punctuation_chars=";&|>"` correctly handles shell metacharacters without splitting on characters inside quotes.

**Destructive detection examples:**

```python
**Docstring-Based Rule Extraction:**
To reduce base token usage per turn, Orion migrates detailed tool-usage rules (e.g. "always search before reading") from the system prompt into the tool function docstrings. `pydantic-ai` automatically extracts these into the tool's JSON schema, meaning Orion only "pays" for these instructions when actively considering that specific tool.

**Minified System Prompt:**
The global system prompt is kept as lean as possible, focusing only on core behavioral boundaries (safety, concise output, markdown format). Tool-specific instructions are never repeated in the prompt, ensuring the highest performance-to-cost ratio for each AI turn.
    return True

# Flag-aware: sed -i is destructive (in-place edit), sed alone is not
if binary == "sed" and any(t == "-i" or t.startswith("-i") for t in tokens[1:]):
    return True

# Git subcommand-aware: only destructive git operations
if binary == "git" and _is_destructive_git(tokens[1:]):
    return True

# Write-redirect token: `cmd > file` clobbers files
if any(_is_write_redirection_token(tok) for tok in all_tokens):
    return True
```

Each detection function has its own domain knowledge (git, curl, docker, kubectl, systemctl, apt).

**Execution:**

```python
result = await asyncio.to_thread(
    subprocess.run, command,
    shell=True,     # ← important: runs via /bin/sh for pipes, etc.
    capture_output=True,
    text=True,
    timeout=TIMEOUT,   # 30 seconds
    cwd=str(Path.home()),
)
output = (result.stdout + result.stderr).strip()
return output[:3000] if output else "(no output)"
```

Both `stdout` and `stderr` are captured and joined — so error messages from a failing command are returned to the agent as output (useful context for debugging).

---

### `src/orion/tools/browser.py`

Implements **two-tier web page extraction** with an offline guard.

**Offline detection:**

```python
def _is_online() -> bool:
    try:
        with socket.create_connection(("8.8.8.8", 53), timeout=2):
            pass
        return True
    except OSError:
        return False
```

Attempts a TCP connection to Google DNS on port 53 — quick (under 2s timeout) and reliable as a connectivity test.

**`fetch_page` — tiered extraction:**

```python
# Tier 1: trafilatura (fast, no browser process)
downloaded = trafilatura.fetch_url(url)
text = trafilatura.extract(downloaded)
if text and len(text) >= MIN_EXTRACT_CHARS:
    return text[:MAX_EXTRACT_CHARS]

# Tier 2: Playwright (JS-rendered pages)
return await _playwright_extract(url)
```

`trafilatura` downloads and extracts in-process — milliseconds. If the result is too short (JS-rendered page rendered empty HTML), Playwright launches a headless WebKit browser, waits for the page to render fully, extracts the rendered HTML, then passes it through trafilatura.

**Why WebKit?** `playwright install webkit` is the only Playwright browser installed by default in this project (smaller footprint than Chromium/Firefox).

---

### `src/orion/tools/search.py`

Wraps **DuckDuckGo search** via the `ddgs` library.

```python
results = await asyncio.to_thread(lambda: list(DDGS().text(query, max_results=max_results)))
```

`DDGS().text()` is synchronous, so it's offloaded to a thread. Results are formatted as markdown with bold title, URL, and body snippet.

`web_search_raw()` returns the raw dict list (used internally by `tools/media.py`), while `web_search()` returns a formatted markdown string (registered as the agent's tool).

**Result cap:**

```python
max_results = min(max_results, 10)
```

The agent can request up to 10 results — hard-capped to prevent excessive API usage.

---

### `src/orion/tools/media.py`

A thin **media-specific search layer** on top of `web_search_raw`.

```python
SITE_FILTERS = {
    "youtube":    "site:youtube.com",
    "spotify":    "site:open.spotify.com",
    "soundcloud": "site:soundcloud.com",
}

site_filter = SITE_FILTERS.get(site, f"site:{site}")
results = await web_search_raw(f"{query} {site_filter}", max_results=5)
```

Appends a DuckDuckGo `site:` filter to the search query to scope results to a specific platform.

**Watch URL preference:**

```python
def is_watch_url(href: str) -> bool:
    return "youtube.com/watch" in href or "youtu.be/" in href

watch_url = next((r.get("href") for r in results if is_watch_url(r.get("href", ""))), None)
url = watch_url or results[0].get("href")
```

Prefers `youtube.com/watch?v=...` links over channel pages, playlists, or search result pages — directly opening the video the user likely wants.

---

## Layer 6 — Agent Core

### `src/orion/core/trace_logging.py`

A **thread-safe, context-variable-scoped JSONL logger** for full turn tracing.

**Context variables (not threading.locals):**

```python
_session_id_var: ContextVar[str | None] = ContextVar("trace_session_id", default=None)
_turn_id_var:    ContextVar[str | None] = ContextVar("trace_turn_id",    default=None)
_request_id_var: ContextVar[str | None] = ContextVar("trace_request_id", default=None)
```

`ContextVar` is asyncio-aware — each asyncio Task gets its own copy of context variables. This means concurrent async tool calls don't interfere with each other's `turn_id` or `request_id` context. `threading.local` would not work reliably here because asyncio tasks share OS threads.

**Event hierarchy:**

```
session_id (entire process lifetime)
  └─ turn_id (one user query → response)
       └─ request_id (one attempt to call the LLM)
            ├─ llm_request
            ├─ llm_response / llm_retry / llm_error
            └─ tool_call_start / tool_call_end (per tool call)
```

**Write safety:**

```python
_write_lock = threading.Lock()

with _write_lock:
    with _log_file_for_today().open("a", encoding="utf-8") as f:
        f.write(line + "\n")
```

File writes are protected by a threading lock because background scan tasks and the main event loop can both write trace events simultaneously.

**Error resilience:**

```python
try:
    with _write_lock:
        with _log_file_for_today().open("a") as f: ...
except OSError:
    return   # tracing must never crash the runtime
```

Trace logging is fire-and-forget — any I/O error is silently swallowed. A logging failure must never break a user's interaction.

**Log retention:**

```python
def cleanup_old_logs(now=None) -> int:
    cutoff = current_time - timedelta(days=TRACE_LOG_RETENTION_DAYS)
    for path in TRACE_LOG_DIR.glob("trace-*.jsonl"):
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        if modified < cutoff:
            path.unlink(missing_ok=True)
```

Deletes daily trace files older than `TRACE_LOG_RETENTION_DAYS` (default 7). `missing_ok=True` prevents a race if two processes try to delete the same file.

---

### `src/orion/core/model_fallback.py`

A minimal file containing the **Groq fallback model chain**.

```python
GROQ_TOKEN_LIMIT_FALLBACK_MODELS: tuple[str, ...] = (
    "groq:openai/gpt-oss-120b",
    "groq:qwen/qwen3-32b",
    "groq:llama-3.3-70b-versatile",
)
```

Defined as a `tuple` (immutable) to prevent accidental mutation. The chain is ordered by capability — start with the most capable Groq model and fall back to smaller ones when the context window is exhausted.

This list is isolated in its own file so it can be updated (or mocked in tests) without touching streaming logic.

---

### `src/orion/core/context.py`

Assembles the **three-tier context string** prepended to every turn.

```python
async def build_context(conn, query, session_id) -> str:
    parts = []

    # Tier 1: User profile — always injected
    profile = get_user_profile(conn)
    if profile:
        parts.append(f"USER PROFILE:\n{...}")

    # Tier 2: Recent conversation — always injected, capped by CONTEXT_RECENT tokens
    recent = get_recent_turns(conn, session_id, max_tokens=CONTEXT_RECENT)
    if recent:
        parts.append(f"RECENT CONVERSATION:\n{recent}")

    # Tier 3: Semantic retrieval — MIN_RRF_SCORE threshold applied inside hybrid_search
    results = await hybrid_search(conn, query, k=5)
    if results:
        parts.append(f"RELEVANT MEMORY:\n{...}")

    return "\n\n".join(parts)
```

The result is a single string injected before the user's query inside `run_with_streaming`. All three tiers contribute factual grounding:
- **Profile**: who the user is.
- **Recent turns**: what was just discussed.
- **Retrieved memory**: older relevant conversations or file snippets.

---

### `src/orion/core/agent.py`

Builds the **PydanticAI agent** with all tools registered and a dynamic system prompt.

**Agent construction:**

```python
agent = Agent(
    selected_model_string,          # e.g. "openai:gpt-4o-mini"
    system_prompt=_build_system_prompt(),
    model_settings={"parallel_tool_calls": False},
)
```

`parallel_tool_calls=False` forces the model to call tools sequentially — one at a time. This is important for correctness: if the agent tries to call `find_files` and `read_file` in parallel, `read_file` might fire before `find_files` returns the path to read.

**System prompt injection of environment:**

```python
def _build_system_prompt() -> str:
    cwd   = os.getcwd()
    shell = os.environ.get("SHELL", "bash")
    home  = Path.home()
    return f"""...
ENVIRONMENT:
- Current directory: {cwd}
- Shell: {shell}
- Home: {home}
..."""
```

The prompt is built at agent-creation time (not at each turn), so it reflects the environment at startup. The home directory, current directory, and shell are baked in — giving the agent accurate context for commands.

**Tool registration with trace wrapping:**

```python
for tool in [find_files, list_directory, read_file, ...]:
    agent.tool_plain(_wrap_tool_for_trace(tool))
```

`agent.tool_plain` registers a callable as a tool without pydantic-ai's automatic argument schema injection (the tools have their own docstrings with `Args:` sections that pydantic-ai uses for schema generation).

**`_wrap_tool_for_trace(tool)`** — transparent trace decorator:

```python
if inspect.iscoroutinefunction(tool):
    @functools.wraps(tool)
    async def _wrapped(*args, **kwargs):
        tool_call_id = trace_logging.log_tool_call_start(...)
        started = time.perf_counter()
        try:
            result = await tool(*args, **kwargs)
            trace_logging.log_tool_call_end(status="ok", result=result, ...)
            return result
        except Exception as e:
            trace_logging.log_tool_call_end(status="error", error=str(e), ...)
            raise
```

Uses `functools.wraps` to preserve the original function's `__name__` and docstring (critical for pydantic-ai's tool schema generation). Handles both sync and async tools with separate code paths.

---

### `src/orion/core/streaming.py`

The **streaming runner and retry orchestrator** — the most complex file in the core.

**`_run_single_model`** — handles one model with up to 3 attempts:

```python
for attempt in range(3):
    async with agent.run_stream(full_prompt) as result:
        async def live_tokens():
            async for delta in result.stream_text(delta=True):
                yield delta
        full_response = await stream_response(live_tokens())

    # Check 1: Did the model leak tool-call markup in plain text?
    if _looks_like_textual_tool_call(full_response) and attempt < 2:
        full_prompt = full_prompt + _TEXTUAL_TOOL_CALL_RETRY_HINT
        continue

    return full_response, None, False, True

except Exception as e:
    # Check 2: Is this a Groq token-limit error?
    if _is_groq_token_limit_error(str(e)):
        return "", err_str, True, False   # (response, error, token_limit=True, ok=False)

    # Check 3: Groq XML hallucination?
    if "failed_generation" in err_str and attempt < 2:
        full_prompt = full_prompt + _TOOL_RETRY_HINT
        continue
```

**Return tuple semantics** `(response, error_text, token_limit_error, ok)`:
- `ok=True`: successful response.
- `token_limit_error=True`: Groq hit its context window — try next model.
- Both false, `ok=False`: non-retryable error.

**`run_with_streaming`** — top-level orchestration:

```python
if PROVIDER != "groq":
    # Simple path: single model, no fallback chain
    response, _, _, _ = await _run_single_model(...)
    return response

# Groq path: iterate through fallback chain
for model_index, fallback_model in enumerate(fallback_models):
    response, err_str, token_limit_error, ok = await _run_single_model(...)
    if ok: return response
    if token_limit_error and model_index < len(fallback_models) - 1:
        continue   # try next fallback
    return ""      # exhausted or non-token-limit failure
```

The Groq fallback only triggers for token-limit errors — other errors (network, auth, etc.) immediately return `""` with no fallback, preserving existing error-surfacing behaviour.

**Textual tool-call detection patterns:**

```python
_TEXTUAL_TOOL_CALL_PATTERNS = (
    re.compile(r"<\s*/?\\s*function",  re.IGNORECASE),
    re.compile(r"<\s*/?\\s*tool_call", re.IGNORECASE),
)
```

Some models (especially older Groq variants) sometimes output `<function>call_name</function>` in plain text instead of using the structured tool-calling API. Detection triggers a retry with a corrective hint appended to the prompt.

---

## Data Flow: A Full Turn

Here's what happens when you type `"open the latest markiplier video"` in interactive mode:

```
1. main.py: get_input() awaits user text from prompt_toolkit

2. main.py: run_once("open the latest markiplier video", mode="interactive")
   ├─ trace_logging.start_turn(...)       → creates turn_id, writes turn_start event
   ├─ safety_confirm.reset_turn_state()   → clears denial cache for this turn
   ├─ save_turn(conn, ..., "user", ...)   → persists to conversations table
   ├─ build_context(conn, ...)            → assembles profile + recent history + relevant memory
   │   ├─ get_user_profile(conn)          → e.g. {"name": "Jadon", "role": "developer"}
   │   ├─ get_recent_turns(conn, ...)     → last N turns within 2000 token budget
   │   └─ hybrid_search(conn, query, k=5) → embeds query, runs FTS + vec search, RRF fuses
   │
   └─ run_with_streaming(agent, query, context=context_string)
       ├─ base_prompt = f"{context}\n\n{query}"
       ├─ _run_single_model(agent, prompt, ...)
       │   ├─ trace_logging.start_llm_request(...)
       │   ├─ spinner.start("thinking")
       │   ├─ agent.run_stream(full_prompt)
       │   │   → LLM decides: call open_media("markiplier", site="youtube")
       │   │   → pydantic-ai invokes _wrap_tool_for_trace(open_media)(...)
       │   │       ├─ trace_logging.log_tool_call_start(...)
       │   │       ├─ web_search_raw("markiplier site:youtube.com")
       │   │       │   └─ asyncio.to_thread(DDGS().text(...))
       │   │       ├─ picks watch URL: https://youtube.com/watch?v=...
       │   │       ├─ subprocess.Popen(["xdg-open", url])   ← browser opens
       │   │       ├─ trace_logging.log_tool_call_end(status="ok", result="Opening: ...")
       │   │       └─ returns "Opening: [video title]\nhttps://..."
       │   ├─ LLM receives tool result, streams final response tokens
       │   ├─ stream_response(live_tokens())   ← Rich.Live renders markdown in real-time
       │   └─ trace_logging.log_llm_response(...)
       └─ returns full response text

3. main.py: save_turn(conn, ..., "assistant", response)
4. main.py: trace_logging.end_turn(status="ok", ...)
5. main.py: print_separator()
```

---

## Key Design Patterns

**1. Dependency injection over global singletons**

The SQLite connection is created once in `main.py` and injected into tools via `set_connection()` and passed to all memory functions explicitly. This makes testing trivial — tests can inject an in-memory SQLite connection.

**2. Asyncio everywhere, threads for blocking I/O**

All tool functions are `async def`, enabling the agent to interleave spinner updates with tool execution. Any blocking call (subprocess, file I/O, fastembed, DDGS) is wrapped in `asyncio.to_thread()`.

**3. Defence in depth for destructive operations**

Every destructive operation passes through at minimum two gates:
- `boundaries.py` — rejects out-of-HOME paths, blocks sudo/danger patterns.
- `confirm.py` — interactive user confirmation with per-turn denial memory.

The system prompt additionally instructs the model to never re-confirm in plain text after a tool reports denial.

**4. Trace logging as a first-class concern**

The trace logging system uses `ContextVar` (not `threading.local`) to track `session_id`, `turn_id`, and `request_id` across asyncio context switches. Every code path that can fail — LLM errors, tool errors, retries — writes a structured JSONL event. This makes production debugging possible by replaying `~/.orion/logs/trace-YYYY-MM-DD.jsonl`.

**5. Tools are plain callables, not classes**

PydanticAI discovers tool signatures via `__doc__` (for the description) and type annotations (for the schema). Using plain functions with `Args:` docstrings keeps tools easy to read, test, and register. The `_wrap_tool_for_trace` decorator is applied at registration time, keeping tool implementations free of tracing concerns.

**6. Config as the single source of truth**

All constants — paths, model settings, context budgets, provider names — live in `config.py`. No magic strings scattered across modules. Tests can override `CONFIG_FILE` before importing `config` to get isolated configuration without touching the filesystem.
