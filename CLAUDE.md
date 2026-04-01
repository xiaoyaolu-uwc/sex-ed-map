# Haven 2.0 MVP

Mental health support tool that guides users to relevant therapeutic content via structured dialogue.

## How It Works

Two-model pipeline over a hand-curated knowledge map (JSON tree of therapeutic topics + source excerpts):

1. **Navigator** (fast/cheap model) — reads user message + conversation state + current map position → outputs structured JSON deciding where to move on the tree
2. **Responder** (quality model) — reads navigator output + node content → generates empathetic user-facing message with citations

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
- Navigator output is always structured JSON with fields: `action`, `target_node`, `reasoning`, `context_for_responder`
- All therapeutic content in responses must cite sources from the knowledge map. No hallucination.
- Config (API keys, model selection) lives in `config.py` and uses environment variables

## Running

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Read First

- `PRD.md` in this folder has the full product requirements
- `prompts/` contains the system prompts — these are the most-iterated part of the system
