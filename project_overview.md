# Orion — Local AI Assistant

**Invoke:** `orion open the latest markiplier video`  
**Stack:** PydanticAI · Ollama + Qwen3-4B · SQLite + sqlite-vec · Rich + prompt_toolkit  
**Hardware target:** 16GB RAM · RTX 1650/3050 (4GB VRAM) · Linux  
**Philosophy:** Minimal yet beautiful — purposeful, not cluttered  
**Theme:** Catppuccin Mocha

---

## What It Is

Orion is a fully local, offline-capable CLI AI assistant. It runs entirely on your machine — no cloud, no API keys, no telemetry. You talk to it in plain English from any terminal.

```bash
orion open the latest markiplier video
orion find my signals notes
orion what went wrong
cat build.log | orion "summarize the errors"
```

---

## Project Structure

```text
~/.orion/                          ← runtime data (DB, history, config)
~/Programming/Projects/cli-assistant/
├── project_overview.md            ← this file
├── cli-assistant-dev-plan.md      ← full technical spec
├── main.py                        ← entry point
├── config.py                      ← constants and settings
├── requirements.txt
│
├── core/
│   ├── agent.py                   ← PydanticAI agent setup
│   ├── context.py                 ← 3-tier context assembly
│   └── streaming.py               ← token stream → Rich renderer
│
├── memory/
│   ├── db.py                      ← SQLite connection + migrations
│   ├── store.py                   ← read/write facts, conversations
│   ├── retrieval.py               ← hybrid FTS5 + sqlite-vec search
│   ├── embeddings.py              ← nomic-embed-text via Ollama
│   └── indexer.py                 ← home directory file scanner
│
├── tools/
│   ├── files.py                   ← file management
│   ├── shell.py                   ← safe shell execution
│   ├── browser.py                 ← xdg-open + Trafilatura + Playwright
│   └── search.py                  ← DuckDuckGo web search
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

Stages are load-bearing — never skip. Each has a pass condition before moving on.

| Stage | Goal | Status |
| ----- | ---- | ------ |
| 1 | Inference baseline — Ollama + Qwen3 streaming | — |
| 2 | Minimal UI shell — Catppuccin theme, spinner, startup screen | — |
| 3 | Agent + tools — file management, shell, URL opener | — |
| 4 | Memory layer — SQLite, hybrid search, file indexer, context injection | — |
| 5 | Web tools — DuckDuckGo search, page extraction | — |
| 6 | Safety layer — path validation, sudo block, destructive confirmation | — |
| 7 | Polish — slash commands, pipe support, model pre-warm, undo | — |

---

## Models

| Model | Use case | Size |
| ----- | -------- | ---- |
| `qwen3:4b` | Primary model — all queries | ~2.7GB |
| `nomic-embed-text` | Embeddings for semantic memory search | small |

Single model — qwen3:4b fits fully in 4GB VRAM and runs at 15–25 t/s on this hardware.

---

## Safety Boundaries

- All file operations restricted to `$HOME` — no escaping
- `sudo`, `su`, `pkexec`, `doas` are hard-blocked
- Danger patterns (`rm -rf`, `dd if=`, etc.) are blocked at the shell layer
- Destructive actions (delete, overwrite) require verbal confirmation before execution

---

## Slash Commands (Stage 7)

| Command | Action |
| ------- | ------ |
| `/help` | Show available commands |
| `/think` | Force chain-of-thought reasoning |
| `/think` | Force chain-of-thought (slower but deeper reasoning) |
| `/clear` | Clear terminal |
| `/undo` | Undo last file operation |
| `/history` | Show session history |
| `/memory` | Show memory summary |
| `/scan` | Re-index home directory |
| `/exit` | Quit |

---

## Installation (final)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Project setup
cd ~/Programming/Projects/cli-assistant
uv init --python 3.13
uv add rich prompt_toolkit pydantic-ai openai httpx sqlite-vec ddgs trafilatura playwright psutil
uv run playwright install webkit

# Ollama models
ollama pull qwen3:4b
ollama pull nomic-embed-text

# First run — builds file index
uv run main.py --init

# Shell command
cat > ~/.local/bin/orion << 'EOF'
#!/bin/bash
exec uv run --directory ~/Programming/Projects/cli-assistant python main.py "$@"
EOF
chmod +x ~/.local/bin/orion
```
