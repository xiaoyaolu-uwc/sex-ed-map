"""Tree query functions for the knowledge map index.

All functions take `index` as their first argument — the flat dict returned
by knowledge_map.loader.load_map(). No global state.
"""


def get_node(index: dict, node_id: str) -> dict:
    """Return the node record for node_id. Raises KeyError if not found."""
    return index[node_id]


def get_children(index: dict, node_id: str) -> list[dict]:
    """Return node records for all children of node_id."""
    node = index[node_id]
    return [index[child_id] for child_id in node["children"]]


def is_leaf(index: dict, node_id: str) -> bool:
    """True if node_id has no children."""
    return len(index[node_id]["children"]) == 0


def get_sources(index: dict, node_ids: list[str]) -> list[dict]:
    """Return all source_excerpts from the given nodes, flattened.

    Skips nodes with no excerpts. Used by the responder to gather citations
    for all active leaf branches.
    """
    sources = []
    for node_id in node_ids:
        sources.extend(index[node_id].get("source_excerpts", []))
    return sources


def get_initial_branches(index: dict, root_id: str) -> list[dict]:
    """Return the starting active_branches list for a new session.

    Starts with a single branch at the root node.
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
    """Build a full branch object for node_id from the map index.

    Walks the parent_id chain to reconstruct the path from root.
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


def build_subtree_text(
    index: dict,
    node_id: str,
    max_depth: int,
    _depth: int = 0,
) -> str:
    """Render the subtree rooted at node_id as indented text for the navigator prompt.

    The root call (depth 0) is marked '← HERE'.
    Leaf nodes are marked '[leaf]'.
    Expands up to max_depth levels below the root.
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
