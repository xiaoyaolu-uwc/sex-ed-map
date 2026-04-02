import os

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    """Read a required environment variable, failing loudly if missing.

    Input:  name (str) — the environment variable name
    Output: str — the value
    Raises: RuntimeError if the variable is not set or empty
    Used by: module-level constants below, at import time
    """
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Required environment variable '{name}' is not set.")
    return value


ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")

NAVIGATOR_MODEL = os.environ.get("NAVIGATOR_MODEL", "claude-haiku-4-5-20251001")
RESPONDER_MODEL = os.environ.get("RESPONDER_MODEL", "claude-sonnet-4-6")

# Number of conversation turns to pass to models (most recent N)
HISTORY_WINDOW = int(os.environ.get("HISTORY_WINDOW", "20"))

# How many levels below the current node to expand in the navigator's subtree view.
# Set to a large number for full depth (default). Lower this if context gets too long.
MAX_CHILD_DEPTH = int(os.environ.get("MAX_CHILD_DEPTH", "999"))

# Root node ID in the knowledge map
ROOT_NODE_ID = os.environ.get("ROOT_NODE_ID", "root_consent")
