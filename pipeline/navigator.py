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
    """Read the navigator system prompt from prompts/navigator.md.

    Input:  none
    Output: str — the full contents of navigator.md
    Note:   Loaded fresh on every call so prompt edits take effect without
            restarting the app. Kept private — callers use navigate().
    """
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_node_list(index: dict) -> str:
    """Render all valid node IDs as a markdown list for the navigator prompt.

    Injected into every call so the model has a complete, authoritative list
    of node IDs it is allowed to reference. Prevents hallucinated IDs.

    Input:  index (dict) — flat node index from loader.load_map()
    Output: str — markdown block, e.g.:
                ## Valid Node IDs

                - `root_consent` — Consent
                - `what_does_consent_look_like` — What does consent look like?
                ...
    Used by: _build_user_message()
    """
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
    """Assemble the full user-turn message sent to the navigator LLM.

    Combines four sections in order:
      1. Valid node list (from _build_node_list)
      2. Active branches — one ASCII subtree block per branch
         (from build_subtree_text in knowledge.py)
      3. Recent conversation history (last HISTORY_WINDOW turns from config)
      4. The user's latest message

    Input:  user_message (str) — the user's latest input
            conversation_history (list[dict]) — full history of {role, content} dicts
            active_branches (list[dict]) — current branch state from session
            index (dict) — flat node index from loader.load_map()
    Output: str — the assembled prompt text passed as the user message to the API
    Used by: navigate()
    """
    parts = [_build_node_list(index), "---", "## Active Branches", ""]

    for branch in active_branches:
        node_id = branch["current_node"]
        path_str = " → ".join(branch["path"])
        parts.append(f"Path: {path_str}")
        parts.append(build_subtree_text(index, node_id, config.MAX_CHILD_DEPTH))
        parts.append("")

    parts.append("---")

    if conversation_history:
        parts.append("## Conversation History")
        parts.append("")
        recent = conversation_history[-config.HISTORY_WINDOW:]
        for turn in recent:
            role = turn["role"].capitalize()
            parts.append(f"**{role}:** {turn['content']}")
        parts.append("")
        parts.append("---")

    parts.append(f"## User's Latest Message\n\n{user_message}")
    return "\n".join(parts)


def _validate(data: dict, index: dict) -> None:
    """Validate the parsed navigator response against the expected schema.

    Checks:
      - 'reasoning' is a non-empty string
      - 'new_active_branches' is a list
      - every current_node in new_active_branches is a real node ID in the index

    Input:  data (dict) — parsed JSON from the model response
            index (dict) — flat node index, used to verify node IDs exist
    Output: None
    Raises: ValueError with a descriptive message on any schema violation
    Used by: navigate() — called immediately after json.loads()
    """
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

    Full flow:
      1. Load system prompt from prompts/navigator.md
      2. Build user message (node list + active branches + history + user input)
      3. Call config.NAVIGATOR_MODEL via Anthropic API
      4. Strip any markdown fences from the response
      5. Parse JSON and validate against schema
      6. Reconstruct full branch objects from the model's minimal {current_node} output

    Input:  user_message (str) — the user's latest message
            conversation_history (list[dict]) — list of {role, content} dicts
            active_branches (list[dict]) — current branch state from session state;
                each branch: {current_node, path, children}
            index (dict) — flat node index from knowledge_map.loader.load_map()
    Output: dict with two keys:
                "reasoning" (str) — the model's explanation of its decisions
                "new_active_branches" (list[dict]) — updated branches, each a full
                    {current_node, path, children} object (reconstructed via
                    reconstruct_branch in knowledge.py)
    Raises: ValueError if the model response fails schema validation
            json.JSONDecodeError if the response is not valid JSON
    Used by: app.py — called once per conversation turn, before the responder
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
