#!/usr/bin/env python3
"""Pipeline test harness — tests the full navigator + responder turn.

Validates that the responder fires in the correct mode given a navigator
output that lands at (or stays at) a known map position.

Usage:
    python tests/test_pipeline.py          # all scenarios
    python tests/test_pipeline.py --list   # list scenarios

Each test:
  1. Calls navigate() with a crafted message and branch state
  2. Asserts the navigator landed where expected
  3. Calls respond() with the resulting branches
  4. Checks the response is in the correct mode

── Mode detection ──────────────────────────────────────────────────────────
  Elicitive  — no leaves active.
              Check: response contains "?" (asks a question).
              Check: response does NOT contain any citation string.

  Preview    — leaf active, user did not ask for content.
              Check: response contains "?" (checks in with user).
              Check: response does NOT contain verbatim citation strings.

  Advice     — leaf active, user explicitly asked for content.
              Check: response contains a citation string from the source
                     excerpts (e.g. "[source 1]", "[source 2]").
────────────────────────────────────────────────────────────────────────────
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from knowledge_map.loader import load_map
from pipeline.navigator import navigate
from pipeline.responder import respond
from services.knowledge import get_initial_branches, reconstruct_branch

_, INDEX = load_map()
SEP = "─" * 66


# ── Helpers ───────────────────────────────────────────────────────────────────


def b(node_id: str) -> dict:
    """Shorthand: build a full branch object for a node ID."""
    return reconstruct_branch(INDEX, node_id)


def collect_stream(gen) -> str:
    """Collect all chunks from a respond() generator into a single string.

    Input:  gen (Generator[str]) — stream returned by respond()
    Output: str — full response text
    """
    return "".join(gen)


def has_citation(text: str) -> bool:
    """Return True if the text contains any citation pattern from the map.

    Checks for '[source N]' in any capitalisation variant.

    Input:  text (str) — response text to inspect
    Output: bool
    """
    import re
    return bool(re.search(r'\[source\s+\d+\]', text, re.IGNORECASE))


# ── Scenarios ─────────────────────────────────────────────────────────────────


SCENARIOS = [
    # ── S1: Elicitive ─────────────────────────────────────────────────────────
    {
        "name": "S1 — Elicitive mode",
        "description": (
            "Branch is at violations_of_consent (non-leaf). User message is "
            "ambiguous between children. Navigator should stay. Responder "
            "should ask a clarifying question (no citations)."
        ),
        "history": [
            {"role": "assistant", "content": "What's been on your mind?"},
            {"role": "user", "content": "Something happened and I'm still working through it."},
            {"role": "assistant", "content": "Take your time. What's coming up for you around it?"},
        ],
        "branches": [b("violations_of_consent")],
        "message": (
            "I'm not sure how to describe it. There's a lot — I'm questioning "
            "whether it even counts as a violation, how it's affected me, and "
            "what I'm supposed to do now."
        ),
        "expected_nodes": {"violations_of_consent"},
        "expected_mode": "elicitive",
    },

    # ── S2: Preview ───────────────────────────────────────────────────────────
    {
        "name": "S2 — Preview mode",
        "description": (
            "Branch is at was_my_consent_violated (leaf). User shares more "
            "context but does not ask for information. Navigator should stay "
            "at the leaf. Responder should preview what's available and check "
            "in — no citations delivered yet."
        ),
        "history": [
            {"role": "assistant", "content": "What's been on your mind?"},
            {"role": "user", "content": "Something happened with my partner and I haven't been able to stop thinking about it."},
            {"role": "assistant", "content": "That sounds like it's been weighing on you. Can you tell me a bit more?"},
        ],
        "branches": [b("was_my_consent_violated")],
        "message": (
            "They kept pushing after I said I wasn't in the mood. I eventually "
            "gave in just to make it stop. I've felt strange about it ever since "
            "but I don't know if I'm overreacting."
        ),
        "expected_nodes": {"was_my_consent_violated"},
        "expected_mode": "preview",
    },

    # ── S3: Advice ────────────────────────────────────────────────────────────
    {
        "name": "S3 — Advice mode",
        "description": (
            "Branch is already at was_my_consent_violated (leaf). User has "
            "just received a preview and explicitly asks to hear more. "
            "Navigator should stay. Responder should deliver cited advice."
        ),
        "history": [
            {"role": "assistant", "content": "What's been on your mind?"},
            {"role": "user", "content": "My partner kept pushing after I said no. I gave in eventually. I've felt strange about it."},
            {"role": "assistant", "content": "I hear you. I actually have some material that speaks directly to what you're describing — it touches on how pressure and coercion work even in close relationships. Would it help to hear a bit about that?"},
        ],
        "branches": [b("was_my_consent_violated")],
        "message": "Yes, please — I'd really like to hear that.",
        "expected_nodes": {"was_my_consent_violated"},
        "expected_mode": "advice",
    },
]


# ── Runner ────────────────────────────────────────────────────────────────────


def run_scenario(scenario: dict) -> tuple[bool, str, dict]:
    """Run one scenario end-to-end and return (passed, response_text, detail).

    Input:  scenario (dict) — a scenario dict from SCENARIOS
    Output: (passed: bool, response: str, detail: dict with nav/responder info)
    """
    detail = {}

    # Step 1: navigate
    try:
        nav_result = navigate(
            user_message=scenario["message"],
            conversation_history=scenario["history"],
            active_branches=scenario["branches"],
            index=INDEX,
        )
    except Exception as e:
        return False, "", {"error": f"navigate() failed: {e}"}

    actual_nodes = {b["current_node"] for b in nav_result["new_active_branches"]}
    detail["nav_nodes"] = actual_nodes
    detail["nav_reasoning"] = nav_result["reasoning"]

    nav_ok = actual_nodes == scenario["expected_nodes"]

    # Step 2: respond
    try:
        response = collect_stream(
            respond(
                user_message=scenario["message"],
                conversation_history=scenario["history"],
                active_branches=nav_result["new_active_branches"],
                index=INDEX,
            )
        )
    except Exception as e:
        return False, "", {"error": f"respond() failed: {e}", **detail}

    detail["response"] = response

    # Step 3: check mode
    mode = scenario["expected_mode"]
    has_q = "?" in response
    has_cite = has_citation(response)

    if mode == "elicitive":
        mode_ok = has_q and not has_cite
    elif mode == "preview":
        mode_ok = has_q and not has_cite
    elif mode == "advice":
        mode_ok = has_cite
    else:
        mode_ok = False

    detail["has_question"] = has_q
    detail["has_citation"] = has_cite
    passed = nav_ok and mode_ok
    return passed, response, detail


def main() -> None:
    """Run all pipeline scenarios and print a summary report.

    Input:  none
    Output: none (prints to stdout; exits with code 1 if any scenario fails)
    """
    import argparse
    parser = argparse.ArgumentParser(description="Haven pipeline test harness")
    parser.add_argument("--list", action="store_true", help="List scenarios and exit.")
    args = parser.parse_args()

    if args.list:
        print("\nScenarios:")
        for s in SCENARIOS:
            print(f"  {s['name']}")
            print(f"    {s['description'][:80]}...")
        return

    print(f"\nHaven Pipeline Test Harness")
    print(f"Navigator : {config.NAVIGATOR_MODEL}")
    print(f"Responder : {config.RESPONDER_MODEL}")
    print(f"Scenarios : {len(SCENARIOS)}")

    results = []
    for scenario in SCENARIOS:
        print(f"\n{SEP}")
        print(f"  {scenario['name']}")
        print(f"  Mode: {scenario['expected_mode']}  |  Expected nodes: {scenario['expected_nodes']}")
        print(SEP)

        passed, response, detail = run_scenario(scenario)

        if "error" in detail:
            print(f"  ✗ ERROR: {detail['error']}")
        else:
            nav_ok = detail["nav_nodes"] == scenario["expected_nodes"]
            print(f"  Navigator : {'✓' if nav_ok else '✗'}  nodes={detail['nav_nodes']}")
            if not nav_ok:
                print(f"             expected={scenario['expected_nodes']}")
                reasoning = detail["nav_reasoning"]
                if len(reasoning) > 100:
                    reasoning = reasoning[:97] + "..."
                print(f"             reasoning: \"{reasoning}\"")

            print(f"  Responder : {'✓' if passed else '✗'}  has_question={detail['has_question']}  has_citation={detail['has_citation']}")
            print(f"\n  Response preview:")
            preview = response[:300] + ("..." if len(response) > 300 else "")
            for line in preview.splitlines():
                print(f"    {line}")

        results.append((scenario["name"], passed))

    total = len(results)
    passed_count = sum(1 for _, ok in results if ok)
    failed = [(name) for name, ok in results if not ok]

    print(f"\n{SEP}")
    print(f"  Results: {passed_count} passed, {total - passed_count} failed ({total} total)")
    if failed:
        print(f"  Failed : {', '.join(failed)}")
    print(SEP)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
