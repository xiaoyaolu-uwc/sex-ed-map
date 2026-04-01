# Haven 2.0 MVP

Mental health support tool that guides users to relevant therapeutic content via structured dialogue.

## How It Works

Two-model pipeline over a hand-curated knowledge map (JSON tree of therapeutic topics + source excerpts):

1. **Navigator** (fast/cheap model) — reads user message + conversation history + per-branch ASCII subtree (expanded to `max_child_depth`) → outputs `{reasoning, new_active_branches: [{current_node}]}`. Model declares destination nodes only; Python reconstructs `path` and `children` from the map index. Model may jump to any depth descendant in one move.
2. **Responder** (quality model) — reads session state + source excerpts from any leaf nodes currently in `active_branches` → generates empathetic user-facing message with citations

Frontend is Streamlit. Session state is `st.session_state`. No database.

## Repo Structure

```
knowledge_map/    # map.json (the tree) + loader.py
pipeline/         # navigator.py, responder.py
prompts/          # navigator.md, responder.md (system prompts, iterated frequently)
services/         # knowledge.py (tree queries), session.py (state wrapper)
static/           # map.txt (ASCII tree for display)
app.py            # Streamlit entrypoint
config.py         # API keys, model names
```

## Key Conventions

- Prompts live in `prompts/` as markdown files, not as strings in Python code
- The knowledge map is a single JSON file loaded into memory at startup — no database
- Navigator output is always `{"reasoning": "...", "new_active_branches": [{"current_node": "node_id"}, ...]}`. The model only declares destination nodes. Python reconstructs `path` and `children` from the map index after every call.
- A branch is deactivated by omitting it from `new_active_branches`. Fan-out is multiple entries. Any-depth jumps are allowed.
- All therapeutic content in responses must cite sources from the knowledge map. No hallucination.
- Config (API keys, model selection) lives in `config.py` and uses environment variables

## Running

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Version Control

- After every significant file edit (Write or Edit tool calls), auto-commit the changed file via a PostToolUse hook in `.claude/settings.json`
- Commit messages use the format `auto: update <filename>`
- For manual commits (multi-file changes, features), use a descriptive message following the existing commit style

## Read First

- `PRD.md` in this folder has the full product requirements
- `prompts/` contains the system prompts — these are the most-iterated part of the system
