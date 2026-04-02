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
NAVIGATOR_MODEL = _require("NAVIGATOR_MODEL")
RESPONDER_MODEL = _require("RESPONDER_MODEL")

# Number of conversation turns to pass to models (most recent N)
HISTORY_WINDOW = int(_require("HISTORY_WINDOW"))

# How many levels below the current node to expand in the navigator's subtree view.
MAX_CHILD_DEPTH = int(_require("MAX_CHILD_DEPTH"))

# Root node ID in the knowledge map
ROOT_NODE_ID = _require("ROOT_NODE_ID")
