### Known Issues 🐛
- **Groq Model Overrides**: Manual model changes in `config.toml` (e.g. for testing) are currently ignored by the fallback logic if they aren't in the fixed fallback chain.
- **Initialization Resilience**: Caught initialization failures now present a clean panel, but standardizing the environment injection path is ongoing.

## 🚀 Known Gaps & Future Ideas (from ideas)

### Features & CLI
- **`/think` mode**: Explicitly handle/indicate that "Think mode" might not work on all cloud providers.
- **Config Reload**: Support reloading `~/.orion/config.toml` without restarting the app.
- **Runtime Switching**: Add `/model` to switch AI models without editing config files.
- **Integration**: MCP server support and better Pipe (`|`) integration.

### Core Architecture
- **Context Management**: 
    - Implement context shrinking/pruning to avoid hitting token limits on large profiles or retrieved memory.
    - Multi-turn native message history (currently text-injected).

---

## 🏗️ Architecture & Safety Roadmap (from architecture_improvements)

### 1. Robustness & Safety
- **Embedding Dimensions**: Fix the hardcoded `384` dimension in `config.py` and `db.py`. Allow for dynamic vector table creation if the embedding model changes.
- **`validate_sudo`**: Move beyond simple tokenization checks for sudo. Consider `bashlex` for proper AST parsing of shell commands to prevent escaping detection.
- **Git Safety**: Review "overzealous" destructive checks (e.g., `git checkout -- file` requiring confirmation).

### 2. Thread Safety
- **Lazy Loading**: Add locks around `fastembed` model initialization to prevent race conditions during async initialization.

### 3. LLM Context
- **Selective Retrieval**: Ensure retrieved memory from `sqlite-vec` is relevant enough to warrant token usage.
- **File Reading**: Support `start_line` and `end_line` in `read_file` to handle large files without blind-truncation.
