import os

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

NAVIGATOR_MODEL = os.environ.get("NAVIGATOR_MODEL", "claude-haiku-4-5-20251001")
RESPONDER_MODEL = os.environ.get("RESPONDER_MODEL", "claude-sonnet-4-6")

# Number of conversation turns to pass to models (most recent N)
HISTORY_WINDOW = int(os.environ.get("HISTORY_WINDOW", "20"))

# How many levels below the current node to expand in the navigator's subtree view.
# Set to a large number for full depth (default). Lower this if context gets too long.
MAX_CHILD_DEPTH = int(os.environ.get("MAX_CHILD_DEPTH", "999"))

# Root node ID in the knowledge map
ROOT_NODE_ID = os.environ.get("ROOT_NODE_ID", "root_consent")
