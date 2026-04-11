# Orion CLI Assistant

Orion is a terminal-first AI assistant for Linux that combines:

- conversational help,
- tool calling for files, shell, web, and media,
- local memory and retrieval,
- safety boundaries for risky operations,
- streaming UX for fast interactive feedback.

It supports cloud providers (OpenAI, Anthropic, Gemini, Groq, Mistral) through provider-aware model configuration.

## Key Features

- Interactive CLI assistant with streaming responses.
- One-shot mode for direct commands.
- Pipe mode for log and text analysis from stdin.
- Slash commands for runtime control:
  - /help, /think, /clear, /undo, /reset, /history, /memory, /scan, /exit
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
- Full turn trace logs (user input, LLM request/response, tool calls/results) in ~/.orion/logs with 7-day default retention.

## Architecture Overview

The project follows a standard `src/` layout for clean packaging and namespace isolation. The source resides in `src/orion/`:

- Entry and orchestration:
  - `src/orion/main.py`: Routes one-shot, pipe, and interactive modes; manages global state.
- Agent core:
  - `src/orion/core/agent.py`: Builds a provider-aware PydanticAI agent and registers tools.
  - `src/orion/core/streaming.py`: Handles streaming and retry logic.
  - `src/orion/core/context.py`: Assembles profile, recent turns, and retrieved memory.
- Memory subsystem:
  - `src/orion/memory/db.py`: SQLite schema and connection setup.
  - `src/orion/memory/store.py`: Conversation/profile/operation persistence.
  - `src/orion/memory/retrieval.py`: Hybrid FTS + vector search.
  - `src/orion/memory/indexer.py`: Home file metadata indexing.
  - `src/orion/memory/embeddings.py`: Fastembed vector generation.
- Tools:
  - `src/orion/tools/`: Files, shell, browser, search, and media tool modules.
- UI:
  - `src/orion/ui/`: Renderer, spinner, input handlers, and slash command routing.

For a deeper technical breakdown, see [project_overview.md](project_overview.md).

## Repository Structure

```text
cli-assistant/
├── src/
│   └── orion/         # Application source package
├── tests/             # Comprehensive test suite
├── docs/              # Superpower plans and walkthroughs
├── README.md
├── project_overview.md
├── pyproject.toml
└── uv.lock
```

## Installation

### Using uv (Recommended)

To install `orion-cli` as a global tool:

```bash
# From the repository root
uv tool install .
```

This makes the `orion` command available globally. 

> [!NOTE]
> On the first run, Orion will automatically install the Playwright web extraction engine (~150MB) if it's not already present.

### Development Mode

To install in editable mode for active development:

```bash
uv tool install --editable .
```

Alternatively, you can run directly through `uv`:

```bash
uv run orion
```

## Running Orion

Once installed, use the `orion` command:

**Interactive mode:**

```bash
orion
```

**One-shot mode:**

```bash
orion "summarize this repository"
```

**Pipe mode:**

```bash
cat build.log | orion "find root cause"
```

## Configuration

Orion reads runtime configuration from `~/.orion/config.toml`. Use the following to initialize your environment:

1. Create the directory: `mkdir -p ~/.orion`
2. Create `config.toml`:

```toml
model_string = "openai:gpt-4o"  # or "anthropic:claude-3-5-sonnet-latest", etc.
```

3. Export your provider's API key:

```bash
export OPENAI_API_KEY=sk-...
```

For more options, see [config.py](src/orion/config.py).

## Quality and Verification

Orion maintains a high-quality bar with a 170+ test suite covering core logic, tools, and UI primitives.

```bash
uv run pytest
```
