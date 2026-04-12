
```markdown
# TASK: Implement V2 Adaptive Context & Token Efficiency

## System Context
You are modifying `orion-cli`, a Python-based, Linux-first AI CLI assistant. The project uses the `src/orion/` layout.
Our goal is to replace the current "greedy" context assembly with an `AdaptiveContextBuilder` that strictly respects a background token budget, ensuring massive piped inputs (like system logs) do not cause token-limit crashes.

## Rules for this Task
1. Do not modify the database schema.
2. Preserve all existing `rich` UI formatting and `pydantic-ai` agent initializations.
3. Only use the standard library for token estimation (no `tiktoken`).
4. Read the instructions for each file carefully. Provide the updated code for each.

---

## Step 1: Define Budgets
**File:** `src/orion/config.py`
**Action:** Add the following global constants to handle the dual-budget architecture.

```python
# Token Management
# Maximum tokens allocated strictly to background context (Profile + Semantic Memory + History).
SYSTEM_CONTEXT_BUDGET = 2500

# Maximum tokens allowed for the user's active prompt or piped stdin.
# This prevents pipe mode from crashing the provider's context window.
MAX_USER_PROMPT_BUDGET = 120000 
```

---

## Step 2: Implement the Token Estimator
**File:** `src/orion/memory/store.py` (or create `src/orion/utils/tokens.py` if a utils module exists)
**Action:** Add this dependency-free token estimation heuristic. 

```python
import math

def estimate_tokens(text: str) -> int:
    """
    A fast, provider-agnostic heuristic for estimating token count.
    Works reliably across OpenAI (BPE), Anthropic, and Llama tokenizers.
    Accounts for dense code blocks and JSON formatting.
    """
    if not text:
        return 0
    words = len(text.split())
    chars = len(text)
    return max(words, math.ceil(chars / 3.7))
```

---

## Step 3: Implement the Adaptive Context Builder
**File:** `src/orion/core/context.py`
**Action:** Refactor the context assembly logic. Replace the current greedy assembly with this budget-aware priority ladder. Ensure you import `estimate_tokens` from Step 2 and `SYSTEM_CONTEXT_BUDGET` from Step 1.

```python
def build_adaptive_context(
    profile_facts: list[str], 
    semantic_snippets: list[str], 
    recent_history: list[dict]
) -> tuple[str, bool]:
    """
    Builds the system context while strictly adhering to SYSTEM_CONTEXT_BUDGET.
    Returns a tuple of (assembled_context_string, was_pruned_boolean).
    Priority: Profile (Immutable) -> Semantic Memory (High) -> History (Low).
    """
    remaining_budget = SYSTEM_CONTEXT_BUDGET
    assembled_parts = []
    was_pruned = False

    # 1. Tier 1: User Profile (Immutable - Always included)
    if profile_facts:
        profile_text = "USER PROFILE:\n" + "\n".join(f"- {fact}" for fact in profile_facts)
        assembled_parts.append(profile_text)
        remaining_budget -= estimate_tokens(profile_text)

    # 2. Tier 2: Semantic Memory (High Priority)
    if semantic_snippets and remaining_budget > 0:
        assembled_parts.append("\nRELEVANT FILE SNIPPETS:")
        for snippet in semantic_snippets:
            cost = estimate_tokens(snippet)
            if remaining_budget - cost > 0:
                assembled_parts.append(snippet)
                remaining_budget -= cost
            else:
                was_pruned = True
                break # Stop adding snippets if budget is exhausted

    # 3. Tier 3: Conversation History (Lowest Priority)
    if recent_history and remaining_budget > 0:
        assembled_parts.append("\nRECENT CONVERSATION:")
        # Reverse to newest-first to ensure most recent context is prioritized
        recent_history_reversed = reversed(recent_history) 
        
        history_parts = []
        for turn in recent_history_reversed:
            # Assuming 'turn' is a dict with 'role' and 'content'
            turn_text = f"{turn['role'].upper()}: {turn['content']}"
            cost = estimate_tokens(turn_text)
            
            if remaining_budget - cost > 0:
                # Insert at beginning to restore chronological order
                history_parts.insert(0, turn_text) 
                remaining_budget -= cost
            else:
                was_pruned = True
                break
                
        assembled_parts.extend(history_parts)

    return "\n".join(assembled_parts), was_pruned
```

---

## Step 4: System Prompt Minification
**File:** `src/orion/core/agent.py` & `src/orion/tools/*.py`
**Action:** 1. Review the `system_prompt` definition in `agent.py`. Remove any detailed instructions explaining *how* to use specific tools (e.g., shell commands, file reading).
2. Move those detailed instructions into the Python `"""docstrings"""` of the respective tool functions in the `src/orion/tools/` directory. Pydantic-AI will automatically extract these and inject them into the JSON tool schema, saving baseline tokens.

---

## Step 5: UI Transparency for Pruning
**File:** `src/orion/ui/renderer.py`
**Action:** Update the rendering logic to visually indicate if context was dropped. 
When rendering the AI's final response stream to the terminal, check if the `was_pruned` boolean from Step 3 is `True`. 

If `True`, append the following Rich-formatted string to the very end of the AI's output (or render it as a subtle footer):
`"\n\n[dim yellow](Context optimized to save tokens)[/dim yellow]"`

Ensure this does not break the markdown streaming formatting.

```