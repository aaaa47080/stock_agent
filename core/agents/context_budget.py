"""
Context budget enforcement for manager prompt assembly.

Prevents history slot in the LLM prompt from exceeding CONTEXT_CHAR_BUDGET chars.
When the raw history is too long, serve CompactPrompt (Goal/Progress/OpenQ/NextSteps)
instead.
"""
from __future__ import annotations

from dataclasses import dataclass

# Total chars allocated to the history slot in the manager intent-understanding prompt.
# Derived from: typical model context ~128k tokens ≈ 500k chars; history slot ≤ 1.2% of that.
# Adjust when switching to a smaller model.
CONTEXT_CHAR_BUDGET: int = 6_000


@dataclass
class CompactPrompt:
    """Structured compact representation of a long session."""
    goal: str
    progress: str
    open_questions: str = ""
    next_steps: str = ""


def history_exceeds_budget(history: str) -> bool:
    """Return True if history string exceeds CONTEXT_CHAR_BUDGET chars."""
    return len(history) > CONTEXT_CHAR_BUDGET


def format_compact_state(cp: CompactPrompt) -> str:
    """Render CompactPrompt as a compact history block for LLM injection."""
    lines = ["[Session Compact Summary]", f"Goal: {cp.goal}", f"Progress: {cp.progress}"]
    if cp.open_questions:
        lines.append(f"Open Questions: {cp.open_questions}")
    if cp.next_steps:
        lines.append(f"Next Steps: {cp.next_steps}")
    return "\n".join(lines)
