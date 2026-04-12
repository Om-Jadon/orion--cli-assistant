# Cloud-Only Runtime Migration Plan

> For agentic workers: execute task-by-task using subagent-driven-development or executing-plans.

## Goal

Remove local Ollama runtime support and run Orion in cloud API mode only, with explicit fail-fast configuration and updated docs/tests.

## Architecture

The migration removes the split runtime path (local vs cloud) and standardizes agent startup, provider detection, and command behavior around cloud model_string configuration. All local-specific UX and checks are removed (, Ollama health/prewarm), while existing cloud features (including Groq token-limit fallback) remain intact.

## Scope

Included:
- Cloud-only provider/config/runtime behavior
- Removal of 
- Test and documentation migration

Excluded:
- Reintroducing local-by-API mode
- Adding new providers
- Backward compatibility shim for old model key

## Migration Tasks

### Task 1: Cloud-Only Config Contract

Files:
- Modify: /home/jadon/Programming/Projects/cli-assistant/config.py
- Test: /home/jadon/Programming/Projects/cli-assistant/tests/test_config.py

Steps:
1. Remove local model defaults/constants used only for Ollama runtime.
2. Require model_string and fail fast if it is missing.
3. Keep provider detection strict to known cloud prefixes only.
4. Update config tests to remove ollama fallback assumptions and assert required model_string behavior.

### Task 2: Agent Construction Simplification

Files:
- Modify: /home/jadon/Programming/Projects/cli-assistant/core/agent.py
- Test: /home/jadon/Programming/Projects/cli-assistant/tests/test_agent.py

Steps:
1. Remove local/Ollama branch and keep cloud provider agent construction path only.
2. Remove local think-specific wiring.
3. Preserve model_string_override support used by fallback retries.
4. Remove Ollama-specific tests and keep cloud path coverage.

### Task 3: Startup/UX Cleanup

Files:
- Modify: /home/jadon/Programming/Projects/cli-assistant/ui/startup.py
- Modify: /home/jadon/Programming/Projects/cli-assistant/main.py
- Modify: /home/jadon/Programming/Projects/cli-assistant/ui/slash.py
- Test: /home/jadon/Programming/Projects/cli-assistant/tests/test_startup.py
- Test: /home/jadon/Programming/Projects/cli-assistant/tests/test_slash.py

Steps:
1. Remove _check_ollama and prewarm logic.
2. Keep startup checks to provider API key + memory + index.
3. Remove command and associated runtime state.
4. Update main startup display/model selection to cloud-only semantics.
5. Update startup/slash tests for removed local behavior.

### Task 4: Documentation and Migration Notes

Files:
- Modify: /home/jadon/Programming/Projects/cli-assistant/README.md
- Modify: /home/jadon/Programming/Projects/cli-assistant/project_overview.md

Steps:
1. Remove wording that Orion supports local/Ollama runtime.
2. Remove local setup instructions and examples using local model values.
3. Add migration section for existing users:
   - old: model = "qwen3:..."
   - new: model_string = "<provider>:<model>"
   - required matching API key environment variable.

## Verification

1. Run focused tests:
   - uv run pytest tests/test_config.py tests/test_agent.py tests/test_startup.py tests/test_slash.py
2. Run full suite:
   - uv run pytest
3. Manual checks:
   - missing model_string -> immediate actionable startup error.
   - valid model_string + API key -> startup is healthy, no Ollama status row.
   - /help and slash parsing show no command.

## Decisions

- model_string required (no implicit fallback)
- removed entirely
- No local runtime support in this phase
- Groq fallback policy remains unchanged
