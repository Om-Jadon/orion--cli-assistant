# Orion CLI Assistant

Orion is a terminal-first AI assistant for Linux that combines:

- conversational help,
- tool calling for files, shell, web, and media,
- local memory and retrieval,
- safety boundaries for risky operations,
- streaming UX for fast interactive feedback.

It supports both local inference (Ollama) and cloud providers (OpenAI, Anthropic, Gemini, Groq, Mistral) through provider-aware model configuration.

## Key Features

- Interactive CLI assistant with streaming responses.
- One-shot mode for direct commands.
- Pipe mode for log and text analysis from stdin.
- Slash commands for runtime control:
  - /help, /think, /clear, /undo, /history, /memory, /scan, /exit
- Hybrid memory retrieval:
  - SQLite conversation/profile store
  - FTS5 keyword retrieval
  - sqlite-vec semantic retrieval with fastembed vectors
- Web and media tooling:
  - DuckDuckGo search via ddgs
  - page extraction via trafilatura and Playwright fallback
- Safety model:
  - HOME path boundary enforcement
  - sudo/root command blocking
  - destructive action confirmation
- Structured debug logs written to ~/.orion/debug.log.

## Architecture Overview

The runtime is split into focused layers:

- Entry and orchestration:
  - main.py routes one-shot, pipe, and interactive modes, with a dedicated background scan connection
- Agent core:
  - core/agent.py builds a provider-aware PydanticAI agent and registers tools
  - core/streaming.py handles streaming and retry logic
  - core/context.py assembles profile, recent turns, and retrieved memory
- Memory subsystem:
  - memory/db.py schema and connection setup
  - memory/store.py conversation/profile/operation persistence
  - memory/retrieval.py hybrid FTS + vector search
  - memory/indexer.py home file metadata indexing
  - memory/extractor.py profile fact extraction
  - memory/embeddings.py fastembed vector generation using config-sourced model settings
- Tools:
  - tools/files.py, tools/shell.py, tools/browser.py, tools/search.py, tools/media.py (including hardened file-search fallback behavior)
- UI and controls:
  - ui/renderer.py, ui/input.py, ui/spinner.py, ui/startup.py, ui/slash.py
- Safety:
  - safety/boundaries.py and safety/confirm.py

For a deeper technical breakdown, see project_overview.md.

## Repository Structure

```text
cli-assistant/
├── main.py
├── config.py
├── core/
├── memory/
├── tools/
├── ui/
├── safety/
├── tests/
├── project_overview.md
├── pyproject.toml
└── uv.lock
```

## Requirements

- Linux
- Python 3.13+
- uv
- Optional local inference: Ollama

## Installation

1. Install uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

1. Install dependencies

```bash
cd /path/to/cli-assistant
uv sync
```

1. Install Playwright runtime (used for JS-rendered page fallback)

```bash
uv run playwright install webkit
```

1. If using Ollama, pull models

```bash
ollama pull qwen3:4b
```

Note: The project currently uses fastembed for embeddings, so no Ollama embedding model is required.

1. Build or refresh the file index

```bash
uv run main.py
# then run /scan inside Orion
```

## Running Orion

Interactive mode:

```bash
uv run main.py
```

One-shot mode:

```bash
uv run main.py "summarize this repository"
```

Pipe mode:

```bash
cat build.log | uv run main.py "find root cause"
```

## Configuration

Orion reads runtime config from:

```text
~/.orion/config.toml
```

Common fields:

- model (used with Ollama path)
- model_string (used for cloud providers)
- theme
- max_width

Example:

```toml
model = "qwen3:1.7b"
theme = "mocha"
max_width = 100
```

Cloud provider examples:

```toml
model_string = "openai:gpt-4o-mini"
# model_string = "anthropic:claude-sonnet-4-5"
# model_string = "groq:openai/gpt-oss-120b"
```

Set matching API key environment variables as needed:

- OPENAI_API_KEY
- ANTHROPIC_API_KEY
- GEMINI_API_KEY
- GROQ_API_KEY
- MISTRAL_API_KEY

## Safety Guarantees

- File operations are constrained to your HOME directory.
- sudo/su/pkexec/doas shell commands are blocked.
- Dangerous shell patterns are blocked.
- Destructive actions require explicit confirmation.

## Development

Run tests:

```bash
uv run pytest -q
```

Run a specific test file:

```bash
uv run pytest -q tests/test_main.py
```

## Logging and Diagnostics

- Debug logging is configured in main.py.
- Logs are written to:

```text
~/.orion/debug.log
```

Use this file when diagnosing provider, retrieval, and prewarm issues.

## Project Documentation

- project_overview.md is the canonical detailed technical document.
