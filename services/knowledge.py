"""Tree query functions for the knowledge map index.

All functions take `index` as their first argument — the flat dict returned
by knowledge_map.loader.load_map(). No global state.

The index shape (produced by loader.py):
    {
        node_id (str): {
            "node_id": str,
            "topic": str,
            "source_excerpts": list[{"text": str, "citation": str}],
            "children": list[str],   # child node_ids, empty on leaf nodes
            "parent_id": str | None, # None only on the root node
        }
    }
"""


def get_node(index: dict, node_id: str) -> dict:
    """Return the full node record for a given node_id.

    Input:  index (dict), node_id (str)
    Output: node record dict — {node_id, topic, source_excerpts, children, parent_id}
    Raises: KeyError if node_id is not in the index
    Used by: navigator.py, responder.py, app.py
    """
    return index[node_id]


def get_children(index: dict, node_id: str) -> list[dict]:
    """Return the full node records for all direct children of node_id.

    Input:  index (dict), node_id (str)
    Output: list of node record dicts, in map order; empty list if node is a leaf
    Raises: KeyError if node_id is not in the index
    Used by: app.py (map display), navigator.py (subtree rendering)
    """
    node = index[node_id]
    return [index[child_id] for child_id in node["children"]]


def is_leaf(index: dict, node_id: str) -> bool:
    """Return True if node_id has no children (i.e. it holds source excerpts).

    Input:  index (dict), node_id (str)
    Output: bool
    Raises: KeyError if node_id is not in the index
    Used by: responder.py (decides clarify vs. respond mode),
             build_subtree_text (labels leaf nodes in the navigator prompt)
    """
    return len(index[node_id]["children"]) == 0


def get_sources(index: dict, node_ids: list[str]) -> list[dict]:
    """Return all source excerpts from the given nodes, flattened into one list.

    Skips nodes with no excerpts (non-leaf nodes). Order follows node_ids order.

    Input:  index (dict), node_ids (list[str]) — typically the current_node values
            of all active branches that are at leaf nodes
    Output: list of {"text": str, "citation": str} dicts
    Used by: responder.py — passes these excerpts to the responder LLM so it can
             cite sources in its reply
    """
    sources = []
    for node_id in node_ids:
        sources.extend(index[node_id].get("source_excerpts", []))
    return sources


def get_initial_branches(index: dict, root_id: str) -> list[dict]:
    """Return the starting active_branches list for a new session.

    Creates a single branch at the root node, with path=[root_id] and
    children populated from the index.

    Input:  index (dict), root_id (str) — the node_id of the tree root
    Output: list with one branch dict: {current_node, path, children}
    Used by: session.py (initialises session state on first load / reset)
    """
    root = index[root_id]
    return [
        {
            "current_node": root_id,
            "path": [root_id],
            "children": root["children"],
        }
    ]


def reconstruct_branch(index: dict, node_id: str) -> dict:
    """Build a full branch object for node_id by walking the parent_id chain.

    The navigator LLM only outputs a current_node ID. This function fills in
    the full path (root → node_id) and the children list from the index.

    Input:  index (dict), node_id (str)
    Output: branch dict — {current_node, path: [root, ..., node_id], children: [ids]}
    Raises: KeyError if node_id or any ancestor is not in the index
    Used by: navigator.py — called on every node_id in new_active_branches to
             reconstruct full branch objects from the model's minimal output
    """
    path = []
    current = node_id
    while current is not None:
        path.append(current)
        current = index[current]["parent_id"]
    path.reverse()
    return {
        "current_node": node_id,
        "path": path,
        "children": index[node_id]["children"],
    }


def render_map(index: dict, root_id: str, active_branches: list[dict]) -> str:
    """Render the full knowledge tree as a coloured HTML string for the Streamlit sidebar.

    Each node is styled based on its relationship to the active branches:
      - Green bold  : current active node  → appends ' (current)'
      - Yellow      : direct child of any current node  → appends ' (+)'
      - White       : ancestor on the path to a current node  → appends ' (*)'
      - Grey        : all other nodes (no tag)

    Input:  index (dict) — flat node index from loader.load_map()
            root_id (str) — node ID of the tree root
            active_branches (list[dict]) — current branch state from session;
                each branch: {current_node, path, children}
    Output: str — HTML string; wrap in st.markdown(..., unsafe_allow_html=True)
    Used by: app.py — rendered in the sidebar after every turn
    """
    current_nodes = {b["current_node"] for b in active_branches}
    ancestor_nodes = {
        nid
        for b in active_branches
        for nid in b["path"]
        if nid not in current_nodes
    }
    child_nodes = {
        cid
        for b in active_branches
        for cid in index[b["current_node"]]["children"]
        if cid not in current_nodes
    }

    def _style(node_id: str) -> str:
        if node_id in current_nodes:
            return "color:#4ade80;font-weight:bold"
        if node_id in child_nodes:
            return "color:#facc15"
        if node_id in ancestor_nodes:
            return "color:#ffffff"
        return "color:#6b7280"

    def _render_node(node_id: str, prefix: str, child_prefix: str) -> list[str]:
        node = index[node_id]
        css = _style(node_id)
        safe_prefix = prefix.replace(" ", "&nbsp;")
        line = f'<span style="{css}">{safe_prefix}{node["topic"]}</span>'
        lines = [line]
        for i, cid in enumerate(node["children"]):
            is_last = i == len(node["children"]) - 1
            lines.extend(
                _render_node(
                    cid,
                    child_prefix + ("└── " if is_last else "├── "),
                    child_prefix + ("    " if is_last else "│   "),
                )
            )
        return lines

    root = index[root_id]
    css = _style(root_id)
    lines = [f'<span style="{css}">Root: {root["topic"]}</span>']
    for i, cid in enumerate(root["children"]):
        is_last = i == len(root["children"]) - 1
        lines.extend(
            _render_node(
                cid,
                "└── " if is_last else "├── ",
                "    " if is_last else "│   ",
            )
        )

    inner = "<br>".join(lines)
    return f'<pre style="font-family:monospace;font-size:0.85em;line-height:1.5">{inner}</pre>'


def render_map_text(index: dict, root_id: str, active_branches: list[dict]) -> str:
    """Render the full knowledge tree as plain text with ASCII position markers.

    Each node is annotated based on its relationship to the active branches:
      - (*) : current active node
      - (-) : ancestor on the path to a current node
      - (+) : direct child of any current node (next explorable step)
      - (no tag) : all other nodes

    Input:  index (dict) — flat node index from loader.load_map()
            root_id (str) — node ID of the tree root
            active_branches (list[dict]) — current branch state from session;
                each branch: {current_node, path, children}
    Output: str — plain text; pass to st.code() or st.text()
    Used by: app.py — rendered alongside the coloured HTML map for comparison
    """
    current_nodes = {b["current_node"] for b in active_branches}
    ancestor_nodes = {
        nid
        for b in active_branches
        for nid in b["path"]
        if nid not in current_nodes
    }
    child_nodes = {
        cid
        for b in active_branches
        for cid in index[b["current_node"]]["children"]
        if cid not in current_nodes
    }

    def _tag(node_id: str) -> str:
        if node_id in current_nodes:
            return " (*)"
        if node_id in child_nodes:
            return " (+)"
        if node_id in ancestor_nodes:
            return " (-)"
        return ""

    def _render_node(node_id: str, prefix: str, child_prefix: str) -> list[str]:
        node = index[node_id]
        lines = [f"{prefix}{node['topic']}{_tag(node_id)}"]
        for i, cid in enumerate(node["children"]):
            is_last = i == len(node["children"]) - 1
            lines.extend(
                _render_node(
                    cid,
                    child_prefix + ("└── " if is_last else "├── "),
                    child_prefix + ("    " if is_last else "│   "),
                )
            )
        return lines

    root = index[root_id]
    lines = [f"Root: {root['topic']}{_tag(root_id)}"]
    for i, cid in enumerate(root["children"]):
        is_last = i == len(root["children"]) - 1
        lines.extend(
            _render_node(
                cid,
                "└── " if is_last else "├── ",
                "    " if is_last else "│   ",
            )
        )
    return "\n".join(lines)


def build_subtree_text(
    index: dict,
    node_id: str,
    max_depth: int,
    _depth: int = 0,
) -> str:
    """Render the subtree rooted at node_id as indented text for the navigator prompt.

    The root call (depth 0) is marked '← HERE' so the model knows where it is.
    Leaf nodes are marked '[leaf]' so the model knows it can stop there.
    Expands up to max_depth levels below the root — controls how much of the
    tree the model sees per call.

    Input:  index (dict)
            node_id (str) — root of the subtree to render
            max_depth (int) — how many levels below node_id to show
            _depth (int) — internal recursion counter, do not pass
    Output: multi-line string, e.g.:
                violations_of_consent — Violations of Consent  ← HERE
                  why_do_violations_happen — Why do violations happen? [leaf]
                  responding_to_consent_violations — Responding to Consent Violations
                    what_do_i_do_in_the_moment — What do I do in the moment? [leaf]
    Used by: navigator.py (_build_user_message) — injected into the user message
             once per active branch so the model can see where it is and where it can go
    """
    node = index[node_id]
    indent = "  " * _depth
    here = "  ← HERE" if _depth == 0 else ""
    leaf = " [leaf]" if not node["children"] else ""
    line = f"{indent}{node_id} — {node['topic']}{here}{leaf}"

    if not node["children"] or _depth >= max_depth:
        return line

    child_lines = [
        build_subtree_text(index, child_id, max_depth, _depth + 1)
        for child_id in node["children"]
    ]
    return line + "\n" + "\n".join(child_lines)
