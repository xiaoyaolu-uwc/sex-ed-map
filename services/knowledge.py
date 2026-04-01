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
