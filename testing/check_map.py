import json
from knowledge_map.loader import load_map
from services.knowledge import get_node, get_children, is_leaf, get_sources, get_initial_branches

tree, idx = load_map()

print("=== All nodes ===")
for nid, node in idx.items():
    if is_leaf(idx, nid):
        print(f"  [leaf] {nid} — {node['topic']}")
    else:
        print(f"  [branch] {nid} — {node['topic']} → {node['children']}")

print("\n=== get_node('do_i_want_this') ===")
print(json.dumps(get_node(idx, "do_i_want_this"), indent=2))

print("\n=== get_children('violations_of_consent') ===")
for child in get_children(idx, "violations_of_consent"):
    print(f"  {child['node_id']} — {child['topic']}")

print("\n=== get_sources(['do_i_want_this']) ===")
for s in get_sources(idx, ["do_i_want_this"]):
    print(f"  [{s['citation']}] {s['text'][:100]}...")

print("\n=== get_initial_branches ===")
print(json.dumps(get_initial_branches(idx, "root_consent"), indent=2))
