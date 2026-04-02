"""Responder pipeline component.

Single responsibility: call the responder LLM with the current session state
and stream back the user-facing message.

The responder operates in one of three modes (chosen by the model):
  - Elicitive  — no leaf nodes active; ask a targeted narrowing question
  - Preview    — leaf nodes active but user hasn't asked for content; offer it
  - Advice     — leaf nodes active and user has asked; deliver cited answer

Map traversal logic lives in services/knowledge.py, not here.
"""

from collections.abc import Generator
from pathlib import Path

import anthropic

import config
from services.knowledge import get_sources, is_leaf

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "responder.md"


def _load_prompt() -> str:
    """Read the responder system prompt from prompts/responder.md.

    Input:  none
    Output: str — the full contents of responder.md
    Note:   Loaded fresh on every call so prompt edits take effect without
            restarting the app. Kept private — callers use respond().
    Used by: respond()
    """
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _build_user_message(
    user_message: str,
    conversation_history: list[dict],
    active_branches: list[dict],
    index: dict,
) -> str:
    """Assemble the full user-turn message sent to the responder LLM.

    Combines up to four sections in order:
      1. Active branch context — where the conversation sits on the map
         # TODO(step4): replace this placeholder with the rendering function
         # decided in the parallel step-4 task. Options are: an inline
         # formatter over branch["path"] + index lookups, or a new
         # knowledge.py function (e.g. build_branch_context_text). The
         # output should show, per branch: path with topic names, leaf status,
         # and (if leaf) the topic of the leaf node so the model can name it.
      2. Source excerpts — injected whenever any branch is at a leaf node,
         so the model knows what it can offer (preview) or deliver (advice)
      3. Conversation history — last HISTORY_WINDOW turns
      4. The user's latest message

    Input:  user_message (str) — the user's latest input
            conversation_history (list[dict]) — full history of {role, content} dicts
            active_branches (list[dict]) — current branch state from session;
                each branch: {current_node, path, children}
            index (dict) — flat node index from loader.load_map()
    Output: str — the assembled prompt text passed as the user message to the API
    Used by: respond()
    """
    parts = ["## Active Branches", ""]

    # TODO(step4): replace with chosen branch context renderer.
    # For now, emit a minimal placeholder so the code is runnable while
    # the step-4 decision is pending. Once step-4 is resolved, delete
    # this block and insert the real rendering call.
    for branch in active_branches:
        node_id = branch["current_node"]
        path_str = " → ".join(branch["path"])
        node = index[node_id]
        leaf_marker = " [leaf]" if is_leaf(index, node_id) else ""
        parts.append(f"- Path: {path_str}")
        parts.append(f"  Current: {node_id} — {node['topic']}{leaf_marker}")
    parts.append("")

    # Inject source excerpts whenever any branch is at a leaf.
    leaf_node_ids = [
        b["current_node"] for b in active_branches if is_leaf(index, b["current_node"])
    ]
    if leaf_node_ids:
        sources = get_sources(index, leaf_node_ids)
        if sources:
            parts.append("---")
            parts.append("## Available Source Excerpts")
            parts.append(
                "(These are provided so you know what Haven can offer. "
                "Deliver this content only in Advice mode.)"
            )
            parts.append("")
            for i, source in enumerate(sources, 1):
                parts.append(f"**Excerpt {i}** [{source['citation']}]")
                parts.append(source["text"])
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


def respond(
    user_message: str,
    conversation_history: list[dict],
    active_branches: list[dict],
    index: dict,
) -> Generator[str, None, None]:
    """Call the responder LLM and stream back the user-facing reply.

    Full flow:
      1. Load system prompt from prompts/responder.md
      2. Build user message (branch context + sources if any + history + input)
      3. Call config.RESPONDER_MODEL via Anthropic streaming API
      4. Yield each text chunk as it arrives

    The caller (app.py) collects yielded chunks for display and, once the
    stream is complete, reassembles the full message to pass to
    session.update_after_turn().

    Input:  user_message (str) — the user's latest message
            conversation_history (list[dict]) — list of {role, content} dicts
            active_branches (list[dict]) — current branch state from session;
                each branch: {current_node, path, children}
            index (dict) — flat node index from knowledge_map.loader.load_map()
    Output: Generator[str] — yields text chunks from the model stream
    Raises: anthropic.APIError on API failure
    Used by: app.py — called once per turn, after navigator.navigate()
    """
    system = _load_prompt()
    user_content = _build_user_message(
        user_message, conversation_history, active_branches, index
    )

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    with client.messages.stream(
        model=config.RESPONDER_MODEL,
        max_tokens=1024,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    ) as stream:
        for text in stream.text_stream:
            yield text
