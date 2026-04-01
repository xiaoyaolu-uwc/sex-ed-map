# Haven 2.0 MVP — Product Requirements Document

**Version:** 0.1
**Date:** 2026-03-31
**Author:** xiaoyao
**Status:** Draft

---

## 1. What Is Haven

Haven is a mental health support tool that guides users through difficult moments using a structured knowledge base of therapeutic content. Instead of a free-form chatbot that hallucinates or gives generic advice, Haven uses a **knowledge map** — a tree of curated topics drawn from evidence-based sources — and a **two-model conversation pipeline** that navigates the user to the right content through dialogue.

The core insight: most people in distress don't know what they need. Haven asks the right questions to figure out what's relevant, then delivers grounded, cited answers from vetted sources. It never makes things up.

### Background Documents

The full vision is described in two proposal documents (in the HavenInstruct folder):

- **Haven 2.0 Product Proposal** — product vision, user experience, technical architecture, and go-to-market
- **Haven 2.0 Full Proposal** — deeper detail on the knowledge map structure, the two-model pipeline, ingestion, and institutional deployment

This PRD scopes the MVP: the smallest thing we can build to prove the core loop works.

---

## 2. MVP Scope

### What We're Building

1. **A hand-built knowledge map** stored as a JSON file
2. **A two-model conversation pipeline** (navigator + responder)
3. **A Streamlit chat interface** with session state and a static map display

### What We're NOT Building (deferred)

- Automated ingestion pipeline (Q2)
- Voice mode / STT + TTS (Q2)
- User accounts and persistent memory (Q3)
- Action plan generation / action library (Q2–Q3)
- Neo4j or any database (Q2, when tree outgrows JSON)
- Analytics and monitoring dashboard (Q2)
- Branch-trimming for institutional customization (Q3+)
- Crisis detection / safety classifier (Q2 — important but not MVP)
- Custom-designed UI (someone is already designing this separately)

---

## 3. Feature Specifications

### 3.1 Knowledge Map

**What it is:** A tree structure representing therapeutic topics. Each node is a topic. Leaf nodes contain source excerpts with citations. The tree is hand-curated from 5–10 evidence-based source texts.

**Data model (per node):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier (e.g., `"anxiety.physical"`) |
| `topic` | string | Human-readable topic name (e.g., `"Physical Symptoms of Anxiety"`) |
| `description` | string | 1–2 sentence summary of what this node covers |
| `children` | array of node IDs | Subtopics (empty for leaf nodes) |
| `sources` | array of source objects | Excerpts from source texts (leaf nodes only) |

**Source object:**

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | The actual excerpt from the source |
| `citation` | string | Full citation (author, title, year, page) |
| `source_id` | string | Identifier linking back to the source text |

**Storage:** Single JSON file (`knowledge_map/map.json`). Loaded into memory at app startup.

**Requirements:**
- The tree must have at least 2 levels of depth (root → category → specific topics)
- Leaf nodes must have at least one source excerpt with a citation
- Every non-leaf node must have at least 2 children
- The map should cover at least 2–3 distinct therapeutic domains (e.g., anxiety, grief, stress) to demonstrate navigation

### 3.2 Two-Model Conversation Pipeline

This is the core of Haven. Every user message goes through two sequential model calls.

#### Step 1: Navigator

**Purpose:** Update the set of active branches on the knowledge map based on the user's message.

**Model:** Fast and cheap (e.g., GPT-4o-mini, Claude Haiku, or similar). The navigator's job is structured reasoning, not eloquence.

**Input:**
- The user's latest message
- Conversation history (last N turns)
- The current `active_branches` array (see Session State)

**Output:** A structured JSON object:

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

Per-branch decisions made by the navigator (in a single LLM call across all branches):

- **stay**: Branch is unchanged — current node is still the right level of specificity
- **shift_down**: Branch is replaced by one or more of its children. Each selected child becomes its own new branch entry (fan-out allowed). The parent branch is removed.
- **shift_up**: Current node is deactivated; its parent becomes the active node for this branch. Used when the user signals the current topic doesn't apply or they want to broaden scope.

**Requirements:**
- The navigator must ONLY reference nodes that exist in the map. It cannot invent topics.
- All branches are evaluated in a single LLM call.
- Navigation should feel natural — 2–4 clarifying turns max before branches reach leaf nodes.
- The navigator can shift branches up if the user changes topic or says something doesn't apply.
- The `active_branches` array can grow freely as branches shift down to multiple children.

#### Step 2: Responder

**Purpose:** Generate the user-facing message — either a follow-up question (if navigating) or a cited answer (if at a leaf).

**Model:** High-quality (e.g., Claude Sonnet). The responder's job is empathetic, clear, well-written communication.

**Input:**
- Session state: conversation history + `new_active_branches` (output from navigator)
- Source excerpts from any nodes currently in `active_branches` that have them (leaf nodes)

**Output:** A single natural-language message to the user synthesizing across all active branches. Two modes:

1. **Clarifying mode** (when no active branches are at leaf nodes): An empathetic question that helps narrow down what the user needs. Should reflect the range of currently active branches without listing them mechanically.

2. **Response mode** (when one or more active branches are at leaf nodes): A substantive answer drawing from the source excerpts at those nodes. Must include inline citations (e.g., `[Author, Year]`). Should be warm, grounded, and actionable. Never hallucinates beyond what's in the sources.

**Requirements:**
- Responses must cite sources when drawing from them. No uncited therapeutic claims.
- The tone must be warm and non-clinical — like talking to a knowledgeable, caring friend.
- Clarifying questions must feel natural, not like a diagnostic questionnaire.
- The responder reads state directly — there is no handoff object from the navigator beyond the updated `active_branches`.

### 3.3 Session State

**Storage:** `st.session_state` (Streamlit's built-in session state). No external database.

**What's tracked per session:**

| Key | Type | Description |
|-----|------|-------------|
| `conversation_history` | list of dicts | `{"role": "user"\|"assistant", "content": "..."}` |
| `active_branches` | list of branch objects | Current active positions on the map. Each branch: `{current_node, path, children}` |
| `navigator_state` | dict | Last navigator output (`reasoning` + `new_active_branches`) for debugging/display |

**Branch object:**

| Field | Type | Description |
|-------|------|-------------|
| `current_node` | string | Node ID of this branch's active position |
| `path` | list of strings | Node IDs from root to `current_node` (inclusive) |
| `children` | list of strings | Node IDs of `current_node`'s children (empty if leaf) |

**Lifecycle:** Session state exists only while the browser tab is open. No persistence across refreshes. This is fine for MVP.

### 3.4 Streamlit UI

**Layout:** Single-page app with three visible sections:

1. **Chat window** (main area): Standard chat interface. User types messages, Haven responds. Messages stream in real-time using Streamlit's streaming support. Cited sources appear inline in assistant messages.

2. **Session state debug panel** (sidebar or expander): Shows the current `active_branches` array and the last navigator output (`reasoning` + `new_active_branches`) as raw JSON. This is for development — helps you see exactly what the pipeline is doing.

3. **Static knowledge map display** (sidebar or expander): Renders the full tree structure as a text/ASCII tree. Marks all currently active branch nodes (e.g., `→`). Multiple nodes may be marked simultaneously. Rendered from the JSON at startup and updated each turn.

**Requirements:**
- The chat must stream responses token-by-token (not wait for the full response before displaying)
- The debug panel must update after every turn
- The map display must highlight all active branch positions after every turn
- A "New Conversation" button resets session state

---

## 4. Architecture

### Repo Structure

```
haven/
├── README.md
├── requirements.txt
│
├── knowledge_map/
│   ├── map.json                # The knowledge tree (hand-curated)
│   └── loader.py               # load_map() → returns tree as Python dict
│
├── pipeline/
│   ├── navigator.py            # Calls fast model → new active_branches array
│   └── responder.py            # Calls quality model → user-facing message
│
├── prompts/
│   ├── navigator.md            # System prompt for navigation model
│   └── responder.md            # System prompt for response model
│
├── services/
│   ├── knowledge.py            # Tree traversal: get_node(), get_children(), get_sources()
│   └── session.py              # Thin wrapper around st.session_state
│
├── app.py                      # Streamlit entrypoint
│
├── static/
│   └── map.txt                 # ASCII representation of the knowledge tree
│
└── config.py                   # API keys, model names, settings
```

### Data Flow (One Conversation Turn)

```
User message
    │
    ▼
app.py receives input
    │
    ▼
session.py loads current state (conversation_history, active_branches)
    │
    ▼
navigator.py called with:
  - user message
  - conversation history
  - active_branches (each with current_node, path, children)
    │
    ▼
Navigator returns JSON: {reasoning, new_active_branches}
  - each branch: stay | shift_up (parent replaces child) | shift_down (children replace parent, fan-out allowed)
    │
    ▼
session.py updates active_branches, navigator_state
    │
    ▼
knowledge.py fetches source excerpts for any leaf nodes in active_branches
    │
    ▼
responder.py called with:
  - session state (conversation history + new_active_branches)
  - source excerpts from active leaf nodes
    │
    ▼
Responder streams response back to UI
    │
    ▼
app.py displays message + updates debug panel + marks all active branch nodes on map
```

### Key Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Knowledge map storage | JSON file | Tree is tiny (5–10 sources). Human-readable, git-diffable, no infra. Migrate to DB when ingestion pipeline is built. |
| Frontend framework | Streamlit | Free session state, built-in streaming, no separate frontend build. Disposable — real UI is being designed separately. |
| Navigator model | Fast/cheap (Haiku-class) | Navigation is a structured reasoning task, not a creative one. Save cost and latency. |
| Responder model | High-quality (Sonnet-class) | User-facing empathetic communication. This is where quality matters. |
| Prompts in separate files | `prompts/` folder | Most-iterated part of the system. Easy to version, diff, review by non-engineers. |
| No database | — | Entire state fits in memory + Streamlit session. Zero ops burden for MVP. |
| No crisis detection | — | Important but deferred. MVP is proving the navigation loop, not safety infrastructure. |

---

## 5. Content Requirements

The knowledge map needs to be seeded with real therapeutic content. For MVP:

- **Minimum 5 source texts** from evidence-based therapeutic frameworks (CBT, DBT, ACT, grief counseling, stress management, etc.)
- **Minimum 2 top-level domains** (e.g., Anxiety, Grief) with subtopics branching 2–3 levels deep
- Every source excerpt must have a real citation
- Content should be representative enough to demonstrate meaningful navigation — a user should be able to start with "I've been feeling overwhelmed" and be guided to specific, relevant content through 2–4 turns of dialogue

---

## 6. Success Criteria

The MVP is successful if:

1. **The navigation loop works:** A user can describe a vague emotional state and be guided to specific, relevant content within 2–4 turns.
2. **Responses are grounded:** Every therapeutic claim in a response traces back to a cited source in the knowledge map. No hallucination.
3. **The system can backtrack:** If a user says "that's not quite right" or changes topic, the navigator moves to a different branch.
4. **It runs locally:** `pip install -r requirements.txt && streamlit run app.py` with API keys configured is all it takes.
5. **The debug panel works:** A developer can watch the navigator's reasoning and map position update in real-time to understand and improve the pipeline.

---

## 7. Open Questions

These don't need to be resolved before building. Flag them as they come up.

1. **Which specific models to use?** Navigator and responder model choices should be configurable in `config.py`. Start with whatever is convenient and iterate.
2. **How to handle the user wanting to explore multiple branches?** The system supports multiple active branches natively. The `active_branches` array can grow freely as branches shift down to multiple children. No artificial cap for MVP.
3. **How much conversation history to pass to models?** Start with full history. If context windows become an issue, truncate oldest turns first.
4. **What happens when the user asks something completely off-map?** The responder should acknowledge this gracefully and redirect. Define the exact behavior during prompt iteration.
