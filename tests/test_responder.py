"""Standalone test harness for the responder pipeline.

Not pytest — run directly:
    python tests/test_responder.py

Tests three scenarios covering the responder's three modes:
  1. Elicitive  — no leaf nodes active; should ask one targeted question
  2. Preview    — leaf nodes active, neutral user message; should offer content
  3. Advice     — leaf nodes active, user explicitly asks; should deliver cited answer

For each scenario the script prints:
  - The active branch state passed to the responder
  - The streamed response, token by token
  - A blank separator between scenarios

Requires ANTHROPIC_API_KEY in environment (or hardcoded in config.py).

# TODO(step4): Once the branch context renderer is finalised, verify that the
# active branch block in each test's output looks correct. If the renderer
# adds topic-name path formatting, cross-check that the model's questions and
# offers reference the right topics.
"""

import sys
from pathlib import Path

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_map.loader import load_map
from pipeline.responder import respond
import config

# ---------------------------------------------------------------------------
# Load map
# ---------------------------------------------------------------------------

_raw_tree, INDEX = load_map(Path(__file__).parent.parent / "knowledge_map" / "map.json")

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _find_a_leaf(index: dict) -> str:
    """Return the first leaf node ID found in the index."""
    for node_id, node in index.items():
        if not node["children"]:
            return node_id
    raise RuntimeError("No leaf nodes found in map — check map.json")


def _find_a_non_leaf(index: dict) -> str:
    """Return the first non-leaf, non-root node ID found in the index."""
    for node_id, node in index.items():
        if node["children"] and node["parent_id"] is not None:
            return node_id
    raise RuntimeError("No non-leaf non-root nodes found in map")


def _branch_for(index: dict, node_id: str) -> dict:
    """Build a minimal branch dict for the given node_id."""
    from services.knowledge import reconstruct_branch
    return reconstruct_branch(index, node_id)


def run_scenario(label: str, user_message: str, active_branches: list[dict]) -> None:
    """Run one test scenario and print the streamed response."""
    print(f"\n{'=' * 60}")
    print(f"SCENARIO: {label}")
    print(f"{'=' * 60}")
    print(f"User message: {user_message!r}")
    print("\nActive branches:")
    for b in active_branches:
        node = INDEX[b["current_node"]]
        leaf = "[leaf]" if not node["children"] else ""
        path = " → ".join(b["path"])
        print(f"  {path} {leaf}")
    print("\nResponder output:")
    print("-" * 40)

    full_response = ""
    for chunk in respond(
        user_message=user_message,
        conversation_history=[],
        active_branches=active_branches,
        index=INDEX,
    ):
        print(chunk, end="", flush=True)
        full_response += chunk

    print("\n" + "-" * 40)
    print(f"[Total chars: {len(full_response)}]")


# ---------------------------------------------------------------------------
# Scenario 1 — Elicitive mode
# Non-leaf node active. Expect: one targeted question, no content delivery.
# ---------------------------------------------------------------------------

non_leaf_id = _find_a_non_leaf(INDEX)

run_scenario(
    label="Elicitive — non-leaf branch active",
    user_message="I've been feeling really overwhelmed lately and I'm not sure why.",
    active_branches=[_branch_for(INDEX, non_leaf_id)],
)

# ---------------------------------------------------------------------------
# Scenario 2 — Preview mode
# Leaf node active, neutral message. Expect: brief offer, no content dump.
# ---------------------------------------------------------------------------

leaf_id = _find_a_leaf(INDEX)

run_scenario(
    label="Preview — leaf branch active, neutral message",
    user_message="I've been feeling really overwhelmed lately and I'm not sure why.",
    active_branches=[_branch_for(INDEX, leaf_id)],
)

# ---------------------------------------------------------------------------
# Scenario 3 — Advice mode
# Leaf node active, user explicitly asks for information.
# Expect: substantive cited response.
# ---------------------------------------------------------------------------

run_scenario(
    label="Advice — leaf branch active, user asks for content",
    user_message="Yes, I'd love to know more about that. Please tell me.",
    active_branches=[_branch_for(INDEX, leaf_id)],
)

print("\n\nAll scenarios complete.")
