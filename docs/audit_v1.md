# Orion CLI — Pre-Release Audit (v1.0)

**Date:** 2026-04-13  
**Auditor:** Claude Code  
**Scope:** Full codebase — logic, UX, safety, tests, configuration, consistency  
**Status:** 8 open issues found across High / Medium / Low severity

---

## Executive Summary

The Orion codebase is well-structured and feature-complete across all 8 planned stages. However, a smaller set of bugs and inconsistencies still need to be resolved before a v1.0 release. The most important remaining issues center on SQLite concurrency assumptions, retrieval and integration test coverage, and a few longer-tail safety and maintenance gaps.

---

## HIGH

---

### 8. `db.py` uses `check_same_thread=False` with no documented concurrency contract

**File:** `src/orion/memory/db.py`  
**Type:** Potential Bug

The SQLite connection is opened with `check_same_thread=False`, which allows it to be shared across threads. The main connection is passed to `file_tools.set_connection()` and `memory_tool.set_connection()`, and a separate thread runs the background indexer with its own dedicated connection (correctly). However, the main connection is used concurrently from the async event loop and from tool calls. If PydanticAI ever executes two tool calls concurrently (even though `parallel_tool_calls: False` is set, the async executor may interleave), this could produce write conflicts.

Document the concurrency assumptions, and consider adding `threading.Lock` guards around write paths or switching to `aiosqlite`.

---

### 11. RRF threshold is untested and its tuning rationale is undocumented

**File:** `src/orion/memory/retrieval.py`  
**Type:** Logic / Missing Documentation

`MIN_RRF_SCORE = 0.01`. With `K=60`, the max possible single-result score is `1/(60+0+1) ≈ 0.0164`. Results ranked 20th or lower produce scores near `0.012` — barely above threshold. There are no tests verifying what happens when:
- FTS returns results but vector search returns zero
- Both searches return weak/empty results
- The threshold is inadvertently filtering all valid results

Document why this threshold was chosen, and add tests for boundary conditions.

---

### 15. No integration tests for the full turn pipeline

**Files:** `tests/` (missing)  
**Type:** Test Gap

All existing tests are unit tests. There are no end-to-end tests that exercise:
- User input → context build → agent run → response save → next turn
- Multiple sequential turns (verifying conversation history is maintained)
- Groq token-limit fallback chain
- Memory indexing followed by retrieval in context

These scenarios are where cross-module bugs appear. Add at least a minimal integration test for the happy-path interactive turn.

---

## LOW

---

### 18. No content size limit on `write_file`

**File:** `src/orion/tools/files.py:246`  
**Type:** Missing Guard

`read_file` caps at 4000 chars, `fetch_page` caps at 6000. `write_file` has no cap and will write whatever the model provides. If a model hallucinates enormous content, this could produce unexpectedly large files. Document the expected maximum or add an explicit cap with a warning.

---

### 19. `_SESSION` in `confirm.py` is a module-level `PromptSession` shared across all calls

**File:** `src/orion/safety/confirm.py:13`  
**Type:** Potential Issue

`_SESSION = PromptSession()` is created at import time. `PromptSession` instances carry state (history, key bindings). If the session is used in parallel or reentrantly (e.g., nested tool calls), it could produce unexpected prompt behavior. This is low risk given `parallel_tool_calls: False`, but worth documenting.

---
### 23. `_denied_action_keys` in `confirm.py` is a module-level set — not scoped to the session

**File:** `src/orion/safety/confirm.py:14`  
**Type:** Design Issue

`_denied_action_keys` persists across turns via `reset_turn_state()` being called at turn start. This is intentional and correct. However, the set is never bounded in size — if a session has thousands of turns with unique file paths, the set grows indefinitely. This is unlikely to matter in practice but worth noting for long-running sessions.

---

### 24. `pyproject.toml` should reference `config.__version__` dynamically — but currently can't

**File:** `pyproject.toml`  
**Type:** Process Issue

The version is hardcoded in two places. For v1.0, adopt `dynamic = ["version"]` with `[tool.hatch.version]` or `importlib.metadata.version("orion-cli")` in `config.py` so there is only one source of truth.

---

## Summary Table

| #   | Severity | File                   | Issue                                                                         |
| --- | -------- | ---------------------- | ----------------------------------------------------------------------------- |
| 8   | High     | `memory/db.py`         | `check_same_thread=False` with no documented or enforced concurrency contract |
| 11  | Medium   | `memory/retrieval.py`  | RRF threshold untested and undocumented                                       |
| 15  | Medium   | `tests/`               | No integration tests for the full turn pipeline                               |
| 18  | Low      | `tools/files.py:246`   | No content size limit on `write_file`                                         |
| 19  | Low      | `safety/confirm.py:13` | Shared module-level `PromptSession` — undocumented re-entrancy risk           |
| 23  | Low      | `safety/confirm.py:14` | `_denied_action_keys` set grows unboundedly across a long session             |
| 24  | Low      | `pyproject.toml`       | Two-place version with no single source of truth                              |

---

## Recommended Fix Priority for v1.0

**Must fix (blockers):**
- #8 — Document concurrency contract
- #15 — Add at least one full-turn integration test

**Should fix:**
- #24 — Consolidate version source of truth
- #11 — Document and test RRF threshold behavior

**Nice to have before v1.0:**
- #18, #19, #23 — Minor safety/polish items
