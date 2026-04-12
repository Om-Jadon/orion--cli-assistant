# Orion CLI Assistant

Orion is a terminal-first AI assistant for Linux that combines:

- conversational help,
- tool calling for files, shell, web, and media,
- local memory and retrieval,
- safety boundaries for risky operations,
- streaming UX for fast interactive feedback,
- **Dynamic Theming** (Mocha, Latte, or System).

It supports cloud providers (OpenAI, Anthropic, Gemini, Groq, Mistral) through provider-aware model configuration.

## Key Features

- **High-Fidelity UI**: Rich formatting, gradients, and Catppuccin themes.
- **Interactive Onboarding**: Fully automated, themed setup flow with configuration hardening.
- **Slash Commands**: Runtime control via `/help`, `/clear`, `/undo`, `/reset`, `/history`, `/memory`, `/config`, `/scan`, `/exit`.
- **Hybrid Memory Retrieval**:
  - SQLite conversation/profile store
  - FTS5 keyword retrieval
  - sqlite-vec semantic retrieval with fastembed vectors
- **Web and Media Tooling**:
  - DuckDuckGo search and Playwright-powered page extraction.
- **Safety Model**:
  - HOME path boundary enforcement and sudo command blocking.
- **Absolute Resilience**: Hardened TOML parsing with safe-fallbacks for invalid configurations.

## Architecture Overview

Orion follows a modern `src/` layout for clean packaging:

- **Entry**: `src/orion/main.py`. Orchestrates all modes and initializes the thread-safe database.
- **Agent Core**: `src/orion/core/agent.py`. Built on PydanticAI with provider-aware tool injection.
- **Memory**: `src/orion/memory/`. Hybrid retrieval engine combining FTS and vector search.
- **UI**: `src/orion/ui/`. Renderer (Rich), Slash registry, and the hardened Onboarding flow.
- **Tools**: `src/orion/tools/`. Domain-specific tools for files, shells, and browsing.

## Installation

### Using uv (Recommended)

To install `orion` as a global tool:

```bash
# From the repository root
uv tool install .
```

### Development Mode

```bash
uv tool install --editable .
# Or run directly:
uv run orion
```

## Quality and Verification

Orion is distribution-ready with a **176-test suite** covering core logic, tool isolation, and UI resilience.

```bash
uv run pytest
```

## Usage

**Interactive Prompt:**
```bash
orion
```
*Tip: Type `/help` inside the session to see all available slash commands.*

**One-shot Mode:**
```bash
orion "summarize this repository"
```

**Pipe Mode:**
```bash
cat server.log | orion "find the critical error"
```

## Configuration

Orion state is stored in `~/.orion/`. 

- **Interactive Setup**: Automatically runs on first launch.
- **Manual Edit**: Use `/config` within Orion to open `config.toml` in your default editor.
- **Resilience**: Even if you misconfigure types in the TOML, Orion will fall back to safe defaults instead of crashing.

---
*🌌 Developed for absolute technical assurance and high-performance agentic assistance.*
