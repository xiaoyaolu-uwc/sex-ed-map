"""Session state wrapper for Haven.

Thin abstraction over st.session_state. All reads and writes to session
state go through this module so app.py stays clean.

Session keys managed here:
    conversation_history  list[dict]  {"role": "user"|"assistant", "content": str}
    active_branches       list[dict]  {current_node, path, children}
    navigator_state       dict|None   last navigator output for debug panel
"""

import streamlit as st

from services.knowledge import get_initial_branches


def initialise(index: dict, root_id: str) -> None:
    """Seed session state with empty history and the root branch.

    Safe to call on every Streamlit rerun — does nothing if state is already
    initialised (i.e. the user is mid-conversation).

    Input:  index (dict) — flat node index from loader.load_map()
            root_id (str) — node ID of the tree root (from config.ROOT_NODE_ID)
    Output: None — writes directly to st.session_state
    Used by: app.py — called once at the top of the script on every rerun
    """
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = [
            {
                "role": "assistant",
                "content": (
                    "Hi, I'm Haven.\n\n"
                    "I'm here to help with questions about consent, boundaries, and "
                    "relationships. Whatever brought you here, we can work through it.\n\n"
                    "I work a little differently to most chatbots. Rather than jumping "
                    "straight to advice, I'll ask you a few questions first so I can "
                    "find content that's actually relevant to your situation. When I do, "
                    "I'll tell you what I found and check it sounds right before sharing "
                    "anything. Everything I offer comes from real sources, cited.\n\n"
                    "To get there I'll need to understand your situation a bit, so "
                    "expect more back-and-forth than you might be used to. The more "
                    "context you share, the more useful I can be.\n\n"
                    "What's brought you here today?"
                ),
            }
        ]
    if "active_branches" not in st.session_state:
        st.session_state.active_branches = get_initial_branches(index, root_id)
    if "navigator_state" not in st.session_state:
        st.session_state.navigator_state = None


def get_state() -> dict:
    """Return the current session state as a plain dict.

    Input:  none
    Output: dict with keys:
                conversation_history (list[dict])
                active_branches      (list[dict])
                navigator_state      (dict | None)
    Used by: app.py — passed to navigator.navigate() and responder.respond()
    """
    return {
        "conversation_history": st.session_state.conversation_history,
        "active_branches": st.session_state.active_branches,
        "navigator_state": st.session_state.navigator_state,
    }


def update_after_turn(
    user_message: str,
    assistant_message: str,
    navigator_result: dict,
) -> None:
    """Persist the results of one completed conversation turn to session state.

    Appends both the user and assistant messages to conversation_history,
    updates active_branches with the navigator's new branches, and stores
    the full navigator result for the debug panel.

    Input:  user_message (str) — the user's message this turn
            assistant_message (str) — the responder's full reply (collected
                from the stream before calling this)
            navigator_result (dict) — the dict returned by navigator.navigate(),
                containing "reasoning" and "new_active_branches"
    Output: None — writes directly to st.session_state
    Used by: app.py — called after the responder stream is complete
    """
    st.session_state.conversation_history.append(
        {"role": "user", "content": user_message}
    )
    st.session_state.conversation_history.append(
        {"role": "assistant", "content": assistant_message}
    )
    st.session_state.active_branches = navigator_result["new_active_branches"]
    st.session_state.navigator_state = navigator_result


def reset(index: dict, root_id: str) -> None:
    """Clear all session state and reinitialise to a fresh conversation.

    Wipes conversation_history, active_branches, and navigator_state, then
    re-seeds them via initialise(). Called by the "New Conversation" button.

    Input:  index (dict) — flat node index from loader.load_map()
            root_id (str) — node ID of the tree root (from config.ROOT_NODE_ID)
    Output: None — writes directly to st.session_state
    Used by: app.py — bound to the "New Conversation" button callback
    """
    for key in ("conversation_history", "active_branches", "navigator_state"):
        if key in st.session_state:
            del st.session_state[key]
    initialise(index, root_id)
