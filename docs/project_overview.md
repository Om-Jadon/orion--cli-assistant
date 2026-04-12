# Orion - Project Overview

## What This Project Is

Orion is a Linux-first CLI AI assistant designed for practical cloud-assisted workflows.

Primary goals:

- Natural-language command and assistance from the terminal.
- Tool-using agent behavior for files, shell, browsing, web search, and media lookup.
- Long-term memory and retrieval over conversation and indexed file metadata.
- Strong safety boundaries for file access and destructive actions.
- Fast interactive UX with streaming output and slash-command controls.

Typical usage:

```bash
orion "open the latest markiplier video"
orion "find my project notes"
orion "what failed in this log"
cat build.log | orion "summarize errors"
```

## Current Status

All planned stages are implemented (Stage 1 through Stage 7), including the follow-up quality refactors:

- Delete safety existence checks.
- Indexed file search with fallback behavior.
- Async offloading for blocking subprocess calls.
- Shared HOME constant from config.
- CLI routing integration tests.
- Directory listing truncation notice.
- Structured debug logging to file.
- **Stage 8 Implementation**: Interactive onboarding flow and dynamic configuration synchronization.
- **Robust Stack-based Undo**: Multi-step file operation reversal with native trash restoration.
- **Agentic Memory Management**: Unified AI-driven profile persistence replacing brittle background scanning.
- **Dynamic UI Themes**: Catppuccin Mocha (dark) and Latte (light) support with context-aware spinners.
- **Absolute Config Resilience**: Hardened TOML parsing with safe-integer fallbacks for invalid user edits.
- **Concurrency Hardening**: Isolated background indexing with dedicated thread-local database connections.
- **Enhanced Self-Knowledge**: System-prompt injection of local environment and configuration paths.
- **Slash Command Expansion**: Integrated `/config` for direct settings management.

## Core Stack

Language/runtime:

- Python 3.13+

Agent and model layer:

- pydantic-ai

Terminal UX:

- rich
- prompt-toolkit

Storage and retrieval:

- sqlite3
- sqlite-vec
- FTS5 (SQLite virtual table)
- fastembed

Web and media:

- ddgs (DuckDuckGo search)
- trafilatura (content extraction)
- playwright (JavaScript-rendered fallback extraction)

Networking/utilities:

- httpx

Testing:

- pytest
- pytest-asyncio

## Dependency Inventory and Usage

Runtime dependencies in pyproject.toml:

- ddgs: web search (tools/search.py)
- fastembed: local embeddings (memory/embeddings.py)
- httpx: provider and startup connectivity checks (ui/startup.py)
- playwright: JS-heavy webpage fallback extraction (tools/browser.py)
- prompt-toolkit: interactive input and confirmation prompts (ui/input.py, safety/confirm.py)
- pydantic-ai: agent and tool-calling orchestration (core/agent.py)
- rich: terminal rendering, markdown streaming, startup/status visuals (ui/renderer.py)
- sqlite-vec: vector index support (memory/db.py)
- trafilatura: page text extraction (tools/browser.py)

Dev dependencies:

- pytest
- pytest-asyncio

## Runtime Configuration and Data

Configured in config.py and ~/.orion/config.toml:

- Required model_string runtime selection.
- Provider detection (openai/anthropic/gemini/groq/mistral).
- API key variable mapping for cloud providers.
- Context budget constants.
- Embedding model and dimensions.
- Embedding model and vec schema dimension are sourced from `EMBED_MODEL` and `EMBED_DIM`.

Runtime files under ~/.orion:

- memory.db: SQLite database (conversation, profile, index, vector metadata).
- history: prompt_toolkit command history.
- config.toml: user overrides.
- debug.log: structured debug logs.
- logs/: per-turn JSONL trace logs (user input, LLM request/response, tool calls/results), with 7-day default retention.

## High-Level Architecture

### 1) Application Entry and Routing

main.py handles process mode routing:

- One-shot mode: executes direct prompt from CLI args.
- Pipe mode: reads stdin and queries model with injected input block.
- Interactive mode: startup UI, prewarm, session loop, slash command dispatch.
- **Onboarding mode**: Triggers on first-run to configure backbone model, API keys, and identity.

It also handles the configuration lifecycle:
- Initializing ~/.orion directory and config.toml.
- Reloading configuration dynamically after setup.
- Persisting onboarding results (identity, preferences) to memory.
- Injecting DB connections and trace-log state across all modules.

### 2) Agent Layer

core/agent.py builds the agent with provider-aware model configuration:

- Cloud path: provider-routed model string.

Tool registration is centralized in build_agent and includes:

- files, shell, browser, search, media tools.
- trace-wrapped tool handlers that log tool name, parameters, result/error, and latency.

System prompt enforces:

- direct answers when no tool is needed,
- safe tool usage expectations,
- anti-literal tool-call output constraints.

### 3) Streaming and Interaction

core/streaming.py:

- Streams token deltas live to UI.
- Handles retries for provider/tool-call formatting failure patterns.
- Detects leaked textual tool-call markup and retries with corrective hinting.
- For Groq only, falls back across a fixed in-code three-model chain on token-limit exhaustion errors.
- Does not fallback for non-token-limit errors.
- Logs each LLM request payload, retry reason, final response, and error metadata.

ui/renderer.py, ui/spinner.py, ui/input.py:

- Rich markdown streaming and styled rendering. 
- Dynamic Themes: Catppuccin Mocha and Latte support with runtime refresh.
- Async spinner status updates.
- Prompt session and keybindings.

ui/slash.py:

- Slash command router and handlers.
- Commands: /help /clear /undo /reset /history /memory /config /scan /exit.

### 4) Memory Layer

memory/db.py:

- Opens SQLite connection with WAL and sqlite-vec.
- Applies schema migrations (tables + virtual tables).
- Vec schema dimension is sourced from config (`EMBED_DIM`).

Schema includes:

- conversations
- user_profile
- files
- operation_log
- memory_fts (FTS5)
- vec_memory (sqlite-vec)
- vec_meta

memory/store.py:

- Conversation persistence.
- Profile upsert/delete/read.
- Operation log write/read for stack-based undo.

memory/embeddings.py:

- Embedding generation via fastembed.
- Embedding model is sourced from config (`EMBED_MODEL`).
- Float serialization for vector storage.

memory/retrieval.py:

- Hybrid retrieval via reciprocal rank fusion of FTS + vector results.
- Structured debug logging on query failures.

memory/indexer.py:

- Incremental home-directory metadata scan.
- Extension filtering and inferred tags.

core/context.py assembles three-tier context for each turn:

- profile facts,
- recent conversation,
- semantic retrieval snippets.

### 5) Tools Layer

tools/files.py:

- find_files: SQLite index lookup first, fallback to `find` with maxdepth-first ordering and safe error fallback.
- list_directory: bounded output with truncation notice.
- read_file/open_file/move_file/delete_file.
- delete_file has path validation, existence check, confirmation, async trash call.
- operation logging for undo and shared connection injection hook.

tools/shell.py:

- Command execution with blocked root/danger checks.
- subprocess execution offloaded via asyncio.to_thread.

tools/browser.py:

- open_url for links/local files.
- fetch_page two-tier extraction (trafilatura, then playwright fallback).
- offline guard and debug logging on tier-1 failures.

tools/search.py:

- DuckDuckGo-backed web search (formatted and raw variants).

tools/memory_tool.py:

- manage_user_memory: Unified tool for the AI to intentionally upsert or delete facts from the permanent profile.

tools/media.py:

- site-filtered media lookup with watch-URL preference and browser open.

### 6) Safety Layer

safety/boundaries.py:

- Path restrictions to HOME.
- sudo/root command blocking.
- dangerous shell pattern checks.

safety/confirm.py:

- Async interactive confirmation prompt.
- destructive keyword detection helper.

## Implemented Feature Set

### Inference and Providers

- Local Ollama support via OpenAI-compatible endpoint.
- Cloud provider routing via model_string.
- Startup prewarm path.

### CLI Modes

- One-shot prompt mode.
- Pipe/stdin analysis mode.
- Interactive REPL mode with history and slash commands.

### Slash Commands

- /help
- /clear
- /undo
- /reset
- /history
- /memory
- /config
- /scan
- /exit

### Web and Media

- Web search with capped result count.
- Web page extraction with JS fallback.
- Media search/open with site filtering.

### Memory and Retrieval

- Conversation persistence per session.
- User profile extraction and recall.
- Indexed file metadata scan and search.
- Hybrid semantic retrieval for contextual responses.

### Safety and Guardrails

- Home-bound path enforcement.
- Privileged command blocking.
- Dangerous shell pattern filtering.
- Destructive action confirmation.

### Logging and Diagnostics

- Structured module-level debug logging.
- Unified file sink: ~/.orion/debug.log.
- Full flow trace logging in JSONL under ~/.orion/logs.
- Default retention: last 7 days (configurable via config.toml).

## File Structure

```text
cli-assistant/
├── config.py
├── conftest.py
├── core/
│   ├── __init__.py
│   ├── agent.py
│   ├── context.py
│   └── streaming.py
├── pyproject.toml
├── project_overview.md
├── README.md
├── src/
│   └── orion/
│       ├── __init__.py
│       ├── config.py
│       ├── main.py
│       ├── core/
│       │   ├── __init__.py
│       │   ├── agent.py
│       │   ├── context.py
│       │   ├── model_fallback.py
│       │   ├── streaming.py
│       │   └── trace_logging.py
│       ├── memory/
│       │   ├── __init__.py
│       │   ├── db.py
│       │   ├── embeddings.py
│       │   ├── indexer.py
│       │   ├── retrieval.py
│       │   └── store.py
│       ├── safety/
│       │   ├── __init__.py
│       │   ├── boundaries.py
│       │   └── confirm.py
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── browser.py
│       │   ├── files.py
│       │   ├── media.py
│       │   ├── memory_tool.py
│       │   ├── search.py
│       │   └── shell.py
│       └── ui/
│           ├── __init__.py
│           ├── input.py
│           ├── renderer.py
│           ├── slash.py
│           ├── spinner.py
│           ├── startup.py
│           └── onboarding.py
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_core_agent.py
│   ├── test_core_context.py
│   ├── test_core_model_fallback.py
│   ├── test_core_streaming.py
│   ├── test_main.py
│   ├── test_memory_db.py
│   ├── test_memory_store.py
│   ├── test_memory_embeddings.py
│   ├── test_onboarding_logic.py
│   ├── test_safety_boundaries.py
│   ├── test_safety_confirm.py
│   ├── test_startup.py
│   ├── test_trace_logging.py
│   ├── test_ui_primitives.py
│   ├── test_ui_slash.py
│   └── test_tools_...
└── uv.lock
```

## Quality and Verification

Test suite coverage includes:

- configuration,
- startup checks,
- rendering/spinner,
- agent and streaming behavior,
- memory DB/store/retrieval/extraction/indexing,
- all tools,
- safety confirmation and boundaries,
- slash commands,
- CLI mode routing integration.

Current verification state:

- Full test suite passing (176 tests).

## Notes for Future Development

Recommended extension points:

- Add new slash commands in src/orion/ui/slash.py.
- Add new tool modules and register in src/orion/core/agent.py.
- Extend schema in src/orion/memory/db.py and wire through src/orion/memory/store.py and retrieval paths.
- Add provider-specific runtime tuning in src/orion/config.py and src/orion/core/agent.py.

This document is the canonical project-level technical overview and replaces separate planning documentation.
