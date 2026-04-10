# Sexual Education Map Traversal

A mental health support tool that guides users to relevant therapeutic content through structured dialogue — not a free-form chatbot. Haven uses a hand-curated knowledge map and a two-model pipeline to navigate users to grounded, cited answers from vetted sources. It never makes things up.

## How It Works

Every user message goes through two sequential model calls:

1. **Navigator** (fast/cheap model) — reads the user message, conversation history, and the current `active_branches` array, then outputs a new `active_branches` array by shifting each branch up, keeping it, or expanding it down to children
2. **Responder** (quality model) — reads the updated session state and any source excerpts from leaf nodes in `active_branches`, then generates a warm, cited response

The knowledge map is a tree of curated therapeutic topics stored as a single JSON file. Leaf nodes contain source excerpts with citations. The navigator moves through this tree until it reaches leaves, at which point the responder synthesizes a grounded answer.

## Repo Structure

```
knowledge_map/    # map.json (the tree) + loader.py
pipeline/         # navigator.py, responder.py
prompts/          # navigator.md, responder.md (system prompts)
services/         # knowledge.py (tree queries), session.py (state wrapper)
static/           # map.txt (ASCII tree for display)
app.py            # Streamlit entrypoint
config.py         # API keys, model names
```

## Setup

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your API keys (or set them as environment variables — see `config.py`).

## Running

```bash
streamlit run app.py
```

The UI has three sections:
- **Chat window** — the main conversation interface with streaming responses and inline citations
- **Debug panel** — shows `active_branches` and the navigator's last `reasoning` output as raw JSON
- **Map display** — ASCII tree of the full knowledge map with active branch nodes marked

## Session State

| Key | Type | Description |
|-----|------|-------------|
| `conversation_history` | list | `{role, content}` dicts |
| `active_branches` | list | Current positions on the map. Each branch: `{current_node, path, children}` |
| `navigator_state` | dict | Last navigator output for debugging |

State lives in `st.session_state` — no database, no persistence across refreshes.

## Navigator Output Format

```json
{
  "reasoning": "Why these branch updates were made",
  "new_active_branches": [
    {
      "current_node": "node_id",
      "path": ["root", "...", "node_id"],
      "children": ["child_id_1", "child_id_2"]
    }
  ]
}
```

## Status

MVP in active development. See `PRD.md` for full product requirements and scope.
