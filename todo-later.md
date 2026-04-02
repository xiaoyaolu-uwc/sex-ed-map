# Todo Later

## Compressed conversation history

**Problem:** `conversation_history` is passed verbatim to both the navigator and responder on every turn. As a session grows this wastes tokens and will eventually approach context limits.

**What to build:** A rolling compression function — something like `compress_history(history, keep_last_n)` — that summarises turns older than `keep_last_n` into a single compact summary entry, then appends the verbatim recent turns. The summary should preserve: topics discussed, user's emotional state/concerns, any explicit user preferences (e.g. "that's not what I meant"), and what content has already been offered or delivered.

**Where it lives:** `services/session.py` is the natural home. It already manages history. The function would be called in `update_after_turn()` before writing back to session state, or lazily in `get_state()` before returning history to callers.

**When to prioritise:** When sessions routinely exceed ~20 turns, or if token costs become meaningful.
