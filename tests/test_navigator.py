#!/usr/bin/env python3
"""Navigator test harness.

Run from the project root:
    ANTHROPIC_API_KEY=sk-... python tests/test_navigator.py

Prints the navigator's JSON output for each scenario. Use this to iterate
on prompts/navigator.md without needing the full Streamlit app.

To add a scenario: append a dict to SCENARIOS following the existing pattern.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge_map.loader import load_map
from services.knowledge import get_initial_branches
from pipeline.navigator import navigate

_, INDEX = load_map()
ROOT_ID = "root_consent"

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "name": "1. Vague opening message",
        "description": "Should stay at root or shift to a broad child — not jump to a leaf.",
        "history": [],
        "branches": get_initial_branches(INDEX, ROOT_ID),
        "message": "I've been feeling confused and upset about something that happened with my partner.",
    },
    {
        "name": "2. Specific query — expect deep jump",
        "description": "User is specific enough to skip levels. Should land at a leaf or near-leaf.",
        "history": [
            {"role": "user", "content": "I've been feeling confused about something with my partner."},
            {"role": "assistant", "content": "I hear you. Can you tell me a bit more about what happened?"},
        ],
        "branches": get_initial_branches(INDEX, ROOT_ID),
        "message": "They kept pushing after I said I wasn't sure. I eventually said yes but I didn't really want to. Was that a violation?",
    },
    {
        "name": "3. Topic pivot — expect shift up or deactivate + new direction",
        "description": "User was in 'violations' but pivots to asking about their own behaviour.",
        "history": [
            {"role": "user", "content": "Was what happened to me a violation?"},
            {"role": "assistant", "content": "It sounds like your boundaries may not have been respected..."},
        ],
        "branches": [
            {
                "current_node": "violations_of_consent",
                "path": ["root_consent", "violations_of_consent"],
                "children": [
                    "why_do_violations_happen",
                    "was_my_consent_violated",
                    "how_do_violations_affect_people",
                    "responding_to_consent_violations",
                ],
            }
        ],
        "message": "Actually I think I might have been the one who didn't handle things well. I'm worried I may have crossed a line with someone.",
    },
    {
        "name": "4. Fan-out — expect two branches",
        "description": "User message clearly maps to two distinct subtopics simultaneously.",
        "history": [
            {"role": "user", "content": "I want to get better at consent in my relationship."},
            {"role": "assistant", "content": "That's a meaningful thing to work on. What feels most relevant right now?"},
        ],
        "branches": [
            {
                "current_node": "building_good_consent_practices",
                "path": ["root_consent", "building_good_consent_practices"],
                "children": [
                    "what_makes_consent_hard",
                    "does_consent_ruin_the_mood",
                    "how_do_i_avoid_crossing_boundaries",
                    "how_do_i_talk_about_boundaries",
                ],
            }
        ],
        "message": "I struggle to bring it up at all, but also when I do I don't know how to have the conversation without it feeling awkward.",
    },
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

SEP = "─" * 64


def run(scenario: dict) -> None:
    print(f"\n{SEP}")
    print(f"  {scenario['name']}")
    print(f"  {scenario['description']}")
    print(SEP)
    print(f"\nMessage: \"{scenario['message']}\"")
    print("\nCurrent branches:")
    for b in scenario["branches"]:
        print(f"  {b['current_node']}  (path depth: {len(b['path'])})")
    print()

    try:
        result = navigate(
            user_message=scenario["message"],
            conversation_history=scenario["history"],
            active_branches=scenario["branches"],
            index=INDEX,
        )
        print("Output:")
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"ERROR ({type(e).__name__}): {e}")


if __name__ == "__main__":
    print(f"\nHaven Navigator Test Harness")
    print(f"Map: {len(INDEX)} nodes  |  Model: ", end="")

    # Import here so it prints after sys.path is set
    import config
    print(config.NAVIGATOR_MODEL)

    for scenario in SCENARIOS:
        run(scenario)

    print(f"\n{SEP}")
    print("Done.")
