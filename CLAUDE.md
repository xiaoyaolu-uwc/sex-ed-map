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

## Documentation Convention

Every function must have a docstring that states:
- What the function does (one line)
- `Input:` — each parameter, its type, and what it represents
- `Output:` — return type and shape
- `Used by:` — which other modules/functions call this
- `Raises:` — any exceptions, if relevant

Example:
```python
def get_sources(index: dict, node_ids: list[str]) -> list[dict]:
    """Return all source excerpts from the given nodes, flattened into one list.

    Input:  index (dict) — flat node index from loader.load_map()
            node_ids (list[str]) — node IDs to collect excerpts from
    Output: list of {"text": str, "citation": str} dicts
    Used by: responder.py
    """
```

Apply this to every function when writing new code or editing existing functions.

## Version Control

- After every significant file edit (Write or Edit tool calls), auto-commit the changed file via a PostToolUse hook in `.claude/settings.json`
- Commit messages use the format `auto: update <filename>`
- For manual commits (multi-file changes, features), use a descriptive message following the existing commit style

## End-of-Build Summary

After any extensive build (3+ files written or significantly edited), close with:
1. What changed at the **feature level** (not file-by-file)
2. Where each thing lives in the repo
3. How the user can test it

## Read First

- `PRD.md` in this folder has the full product requirements
- `prompts/` contains the system prompts — these are the most-iterated part of the system
