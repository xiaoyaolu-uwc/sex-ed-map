import json
from pathlib import Path

MAP_PATH = Path(__file__).parent / "map.json"


def load_map() -> tuple[dict, dict]:
    """Load map.json and return (raw_tree, index).

    raw_tree: the nested dict as-is, for display purposes.
    index: flat {node_id: node_record} for O(1) lookup.

    node_record shape:
        {
            "node_id": str,
            "topic": str,
            "source_excerpts": list[dict],  # [{text, citation}], [] on non-leaves
            "children": list[str],          # child node_ids (not nested objects)
            "parent_id": str | None,        # None for root
        }
    """
    with open(MAP_PATH, encoding="utf-8") as f:
        tree = json.load(f)

    index = {}
    _index_node(tree, parent_id=None, index=index)
    return tree, index


def _index_node(node: dict, parent_id: str | None, index: dict) -> None:
    node_id = node["node_id"]
    children = node.get("children", [])
    child_ids = [c["node_id"] for c in children]

    index[node_id] = {
        "node_id": node_id,
        "topic": node["topic"],
        "source_excerpts": node.get("source_excerpts", []),
        "children": child_ids,
        "parent_id": parent_id,
    }

    for child in children:
        _index_node(child, parent_id=node_id, index=index)
