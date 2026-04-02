"""Haven MVP — Streamlit entrypoint.

Wires the navigator + responder pipeline to a chat UI.

Turn flow (per user message):
  1. navigator.navigate() — updates active_branches
  2. session.update_after_turn() — persists new state (called after stream)
  3. responder.respond() — streams reply token-by-token via st.write_stream()

Sidebar shows:
  - Dynamic knowledge map (colour-coded by branch position)
  - Debug panel: raw active_branches + navigator reasoning as JSON
"""

import streamlit as st

import config
from knowledge_map.loader import load_map
from pipeline import navigator, responder
from services import session
from services.knowledge import render_map, render_map_text

st.set_page_config(page_title="Haven", layout="wide")


@st.cache_resource
def _load_map():
    return load_map()


_, index = _load_map()

session.initialise(index, config.ROOT_NODE_ID)

# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Haven")

    st.subheader("Knowledge Map")
    state = session.get_state()
    st.markdown(
        render_map(index, config.ROOT_NODE_ID, state["active_branches"]),
        unsafe_allow_html=True,
    )

    with st.expander("Map (text view)", expanded=False):
        state = session.get_state()
        st.code(
            render_map_text(index, config.ROOT_NODE_ID, state["active_branches"]),
            language=None,
        )

    st.divider()

    with st.expander("Debug — Session State", expanded=False):
        state = session.get_state()
        st.json(
            {
                "active_branches": state["active_branches"],
                "navigator_state": state["navigator_state"],
            }
        )

# ── Chat window ───────────────────────────────────────────────────────────────

st.header("Haven")

state = session.get_state()

# On first load, generate an opening question from the responder.
if not state["conversation_history"]:
    with st.chat_message("assistant"):
        opening = st.write_stream(
            responder.respond(
                user_message="",
                conversation_history=[],
                active_branches=state["active_branches"],
                index=index,
            )
        )
    st.session_state.conversation_history.append(
        {"role": "assistant", "content": opening}
    )

for turn in state["conversation_history"]:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])

if user_message := st.chat_input("What's on your mind?"):
    with st.chat_message("user"):
        st.markdown(user_message)

    state = session.get_state()

    navigator_result = navigator.navigate(
        user_message=user_message,
        conversation_history=state["conversation_history"],
        active_branches=state["active_branches"],
        index=index,
    )

    with st.chat_message("assistant"):
        response_stream = responder.respond(
            user_message=user_message,
            conversation_history=state["conversation_history"],
            active_branches=navigator_result["new_active_branches"],
            index=index,
        )
        assistant_message = st.write_stream(response_stream)

    session.update_after_turn(
        user_message=user_message,
        assistant_message=assistant_message,
        navigator_result=navigator_result,
    )

    st.rerun()
