"""Navigator pipeline component.

Single responsibility: call the navigator LLM with the current session state
and return an updated active_branches list with full branch objects.

Map traversal logic lives in services/knowledge.py, not here.
"""

import json
from pathlib import Path

import anthropic

import config
from services.knowledge import build_subtree_text, reconstruct_branch

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "navigator.md"


def _load_prompt() -> str:
    # Loaded fresh each call so prompt edits take effect without restart.
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_node_list(index: dict) -> str:
    lines = ["## Valid Node IDs", ""]
    for node_id, record in index.items():
        lines.append(f"- `{node_id}` — {record['topic']}")
    return "\n".join(lines)


def _build_user_message(
    user_message: str,
    conversation_history: list[dict],
    active_branches: list[dict],
    index: dict,
) -> str:
    parts = [_build_node_list(index), "---", "## Active Branches", ""]

    for branch in active_branches:
        node_id = branch["current_node"]
        path_str = " → ".join(branch["path"])
        parts.append(f"Path: {path_str}")
        parts.append(build_subtree_text(index, node_id, config.MAX_CHILD_DEPTH))
        parts.append("")

    parts.append("---")

    if conversation_history:
        parts.append("## Conversation History", )
        parts.append("")
        recent = conversation_history[-config.HISTORY_WINDOW :]
        for turn in recent:
            role = turn["role"].capitalize()
            parts.append(f"**{role}:** {turn['content']}")
        parts.append("")
        parts.append("---")

    parts.append(f"## User's Latest Message\n\n{user_message}")
    return "\n".join(parts)


def _validate(data: dict, index: dict) -> None:
    if not isinstance(data.get("reasoning"), str) or not data["reasoning"].strip():
        raise ValueError("Missing or empty 'reasoning'")
    if not isinstance(data.get("new_active_branches"), list):
        raise ValueError("'new_active_branches' must be a list")
    valid_ids = set(index.keys())
    for i, branch in enumerate(data["new_active_branches"]):
        node_id = branch.get("current_node")
        if node_id not in valid_ids:
            raise ValueError(f"Branch {i}: '{node_id}' is not a valid node ID")


def navigate(
    user_message: str,
    conversation_history: list[dict],
    active_branches: list[dict],
    index: dict,
) -> dict:
    """Call the navigator LLM and return updated branch state.

    Args:
        user_message: The user's latest message.
        conversation_history: List of {"role": ..., "content": ...} dicts.
        active_branches: Current active_branches from session state.
        index: Flat node index from knowledge_map.loader.load_map().

    Returns:
        {
            "reasoning": str,
            "new_active_branches": list[dict],  # full branch objects
        }
    """
    system = _load_prompt()
    user_content = _build_user_message(
        user_message, conversation_history, active_branches, index
    )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=config.NAVIGATOR_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()

    # Strip markdown code fences if the model wraps its output despite instructions.
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    data = json.loads(raw)
    _validate(data, index)

    full_branches = [
        reconstruct_branch(index, b["current_node"])
        for b in data["new_active_branches"]
    ]

    return {
        "reasoning": data["reasoning"],
        "new_active_branches": full_branches,
    }
