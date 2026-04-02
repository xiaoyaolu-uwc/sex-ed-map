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
- For each active branch: an ASCII subtree expanded downward from `current_node` to `max_child_depth` levels (default: full depth). The current node is marked `← HERE`. Leaf nodes are marked `[leaf]`. The branch's path from root is shown as context above the tree.

Example per-branch context block:
```
Path: root → violations_of_consent
  violations_of_consent  ← HERE
    why_do_violations_happen [leaf]
    was_my_consent_violated [leaf]
    how_do_violations_affect_people
      coercive_control [leaf]
      emotional_impact [leaf]
    responding_to_consent_violations
      coping_strategies [leaf]
      talking_to_someone [leaf]
```

**Output:** A structured JSON object:

```json
{
  "reasoning": "Why these branch updates were made",
  "new_active_branches": [
    { "current_node": "node_id" }
  ]
}
```

The model declares only destination `current_node` values. Python reconstructs `path` and `children` from the map index after every call.

Navigation model — for each active branch, the model may:

- **Stay**: output the same `current_node` — topic is at the right level
- **Go deeper**: output any descendant at any depth — including grandchildren or deeper. Use when the user's message is specific enough to skip levels.
- **Go up**: output an ancestor node — use when the user signals the topic doesn't apply and they want to broaden
- **Deactivate**: omit the branch from `new_active_branches` entirely — use when the topic is fully irrelevant
- **Fan-out**: output multiple entries that were previously one branch — use when the user's message maps to multiple distinct subtopics simultaneously

**Requirements:**
- The navigator must ONLY reference nodes that exist in the map. It cannot invent topics.
- All branches are evaluated in a single LLM call.
- Navigation should feel natural — the user should reach relevant leaf content within 2–4 turns for a typical query; specific queries may reach a leaf in one turn.
- The `active_branches` array can grow freely via fan-out.

#### Step 2: Responder

**Purpose:** Guide the user toward relevant therapeutic content with full transparency — asking targeted questions to narrow focus, then offering retrieved content before delivering it, and finally synthesising it into substantive help when the user confirms they want it.

**Model:** High-quality (e.g., Claude Sonnet). The responder's job is empathetic, clear, well-written communication.

**Overarching principle:** Transparency. Haven never dumps information on the user unprompted. It first learns enough to find the right content, then tells the user what it found and asks if that's what they're looking for, then delivers it. The user is always in control of what they receive.

**Input:**
- The user's latest message
- Conversation history (last N turns)
- A rendered view of all active branches (path from root with topic names, leaf status) — lets the model ask well-targeted questions and frame offers accurately
- Source excerpts from any leaf nodes in `active_branches` — injected **always** when leaves are active, even in preview mode, so the model knows what it can offer without hallucinating

**Output:** A single short, conversational message. One of three modes:

1. **Elicitive mode** (no active branches at leaf nodes): One deep, targeted question that will help narrow the conversation to the most relevant content. Should feel natural, not like a diagnostic form. Informed by the active branch topics so it's specific, not generic.

2. **Preview mode** (≥1 leaf node active, user has not yet asked for the content): Tell the user what we found — briefly and warmly — and ask if it sounds like what they're looking for. The leaf content is in context so the model can frame the offer accurately, but it must **not** be delivered yet. Response stays short and conversational.

3. **Advice mode** (≥1 leaf node active, user's last message explicitly indicates they want the retrieved content): Draw from the leaf excerpts and everything known about the user's situation. Give substantive, cited, actionable help. Must include inline citations (e.g., `[Author, Year]`). Still warm and conversational — never a wall of clinical text.

**Mode detection (model's responsibility):**
- Leaf nodes active? → Preview or Advice, else Elicitive
- Leaf nodes active AND user's last message clearly says "yes", "tell me more", "I'd like to know", etc.? → Advice, else Preview

**Requirements:**
- Response must always be conversational — even in Advice mode with 2 000 tokens of source material in context, the reply itself should not balloon
- Responses in Advice mode must cite sources. No uncited therapeutic claims.
- Tone: warm, like a knowledgeable, caring friend. Never clinical.
- Clarifying and preview questions must feel natural, not scripted.
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
├── requirements.txt
│
├── knowledge_map/
│   ├── map.json                # The knowledge tree (hand-curated)
│   └── loader.py               # load_map() → (raw_tree, index)
│
├── pipeline/
│   ├── navigator.py            # build_user_message(), navigate() — LLM call + parse + reconstruct
│   └── responder.py            # Calls quality model → user-facing message
│
├── prompts/
│   ├── navigator.md            # System prompt for navigation model (most-iterated file)
│   └── responder.md            # System prompt for response model
│
├── services/
│   ├── knowledge.py            # All map logic: get_node(), get_children(), get_sources(),
│   │                           #   reconstruct_branch(), build_subtree_text()
│   └── session.py              # Thin wrapper around st.session_state
│
├── tests/
│   └── test_navigator.py       # Standalone test harness script (not pytest)
│
├── app.py                      # Streamlit entrypoint
├── static/
│   └── map.txt                 # ASCII representation of the knowledge tree
│
└── config.py                   # API keys, model names, MAX_CHILD_DEPTH, HISTORY_WINDOW
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
Navigator returns JSON: {reasoning, new_active_branches: [{current_node}]}
  - model declares destination nodes only; any-depth jumps allowed; omitted branch = deactivated
    │
    ▼
Python reconstructs path + children for each new branch from map index
    │
    ▼
session.py updates active_branches (full branch objects), navigator_state
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
