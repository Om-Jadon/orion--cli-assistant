# Orion CLI Assistant

![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)
![OS Linux](https://img.shields.io/badge/os-linux-green.svg)
![License MIT](https://img.shields.io/badge/license-MIT-blue.svg)

Orion is a terminal-first AI assistant for Linux that combines:

- conversational help,
- tool calling for files, shell, web, and media,
- local memory and retrieval,
- safety boundaries for risky operations,
- streaming UX for fast interactive feedback,
- **Dynamic Theming** (Mocha, Latte, or System).

It supports cloud providers (OpenAI, Anthropic, Gemini, Groq, Mistral) through provider-aware model configuration.

## ⚡ Fast Install (Any Linux)

The easiest way to install Orion on any Linux machine is via the automated installation script. It has zero external dependencies and will automatically fetch Python and the `uv` toolchain natively under the hood if you don't already have them.

```bash
curl -sSfL https://raw.githubusercontent.com/Om-Jadon/orion--cli-assistant/main/install.sh | bash
```

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
- **Junk Discovery Filtering**: Built-in exclusion of `node_modules`, `.git`, and `.venv` from all file tools.

## Architecture Overview

Orion follows a modern `src/` layout for clean packaging:

- **Entry**: `src/orion/main.py`. Orchestrates all modes and initializes the thread-safe database.
- **Agent Core**: `src/orion/core/agent.py`. Built on PydanticAI with provider-aware tool injection.
- **Memory**: `src/orion/memory/`. Hybrid retrieval engine combining FTS and vector search.
- **UI**: `src/orion/ui/`. Renderer (Rich), Slash registry, and the hardened Onboarding flow.
- **Tools**: `src/orion/tools/`. Domain-specific tools for files, shells, and browsing.

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

## Advanced Installation

### Manual Source Install

If you already use `uv`, you can install Orion straight from the repository:

```bash
uv tool install git+https://github.com/Om-Jadon/orion--cli-assistant.git
```

### Development Mode

```bash
uv tool install --editable .
# Or run directly:
uv run orion
```

## Quality and Verification

Orion is distribution-ready with a **197-test suite** covering core logic, tool isolation, and UI resilience.

```bash
uv run pytest
```

## Configuration

Orion state is stored in `~/.orion/`. 

- **Interactive Setup**: Automatically runs on first launch.
- **Manual Edit**: Use `/config` within Orion to open `config.toml` in your default editor.
- **Git Undo Mode**: Safety boundaries that allow reversing file deletions/moves.
- **High-ROI Token Efficiency**: Docstring-based rule extraction and automatic junk directory filtering (node_modules, .venv, etc.).
- **Catppuccin UI Themes**: Native Mocha and Latte themes for absolute visual assurance.
