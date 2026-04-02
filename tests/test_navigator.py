#!/usr/bin/env python3
"""Navigator test harness with suite selection and auto-validation.

Usage:
    python tests/test_navigator.py                               # all suites
    python tests/test_navigator.py --suite mechanical            # one suite
    python tests/test_navigator.py --suite fan_out multi_branch  # multiple
    python tests/test_navigator.py --list                        # list suites

Scenarios live in tests/scenarios.py. Add or edit tests there.
This file only handles running, validation, and reporting.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from knowledge_map.loader import load_map
from pipeline.navigator import navigate
from tests.scenarios import get_suites

# ── Setup ────────────────────────────────────────────────────────────────────

_, INDEX = load_map()
SUITES = get_suites(INDEX)
SEP = "─" * 66

# ── Validation ───────────────────────────────────────────────────────────────


def validate(result: dict, scenario: dict) -> tuple[bool, dict | None]:
    """Check navigator output against scenario expectations.

    Input:  result (dict)   — output of navigate(), with new_active_branches
            scenario (dict) — scenario dict with expected_nodes and optionally
                              accept_alternatives
    Output: (passed: bool, detail: dict | None)
            detail is None on pass; on fail contains expected, actual, reasoning.
    """
    actual = {b["current_node"] for b in result["new_active_branches"]}
    expected = set(scenario["expected_nodes"])

    if actual == expected:
        return True, None

    for alt in scenario.get("accept_alternatives", []):
        if actual == set(alt):
            return True, None

    return False, {
        "expected": expected,
        "actual": actual,
        "reasoning": result["reasoning"],
    }


# ── Runner ───────────────────────────────────────────────────────────────────


def run_scenario(scenario: dict) -> tuple[bool, dict | None]:
    """Run one scenario and return (passed, fail_detail).

    Input:  scenario (dict) — a scenario dict from scenarios.py
    Output: (passed: bool, fail_detail: dict | None)
    """
    try:
        result = navigate(
            user_message=scenario["message"],
            conversation_history=scenario["history"],
            active_branches=scenario["branches"],
            index=INDEX,
        )
        return validate(result, scenario)
    except Exception as e:
        return False, {
            "expected": set(scenario["expected_nodes"]),
            "actual": f"ERROR: {type(e).__name__}: {e}",
            "reasoning": "",
        }


def run_suite(suite_name: str, scenarios: list[dict]) -> list[tuple[str, bool, dict | None]]:
    """Run all scenarios in a suite and return results.

    Input:  suite_name (str)       — display name for the suite
            scenarios (list[dict]) — list of scenario dicts
    Output: list of (name, passed, fail_detail) tuples
    """
    print(f"\n{SEP}")
    print(f"  Suite: {suite_name}  ({len(scenarios)} tests)")
    print(SEP)

    results = []
    for scenario in scenarios:
        passed, detail = run_scenario(scenario)
        tag = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {tag}  {scenario['name']}")
        if not passed:
            print(f"           Expected : {detail['expected']}")
            print(f"           Got      : {detail['actual']}")
            if detail["reasoning"]:
                # Truncate long reasoning for readability
                reasoning = detail["reasoning"]
                if len(reasoning) > 120:
                    reasoning = reasoning[:117] + "..."
                print(f"           Reasoning: \"{reasoning}\"")
        results.append((scenario["name"], passed, detail))

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Input:  none (reads sys.argv)
    Output: argparse.Namespace with .suite (list[str] | None) and .list (bool)
    """
    parser = argparse.ArgumentParser(
        description="Haven navigator test harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--suite",
        nargs="+",
        metavar="SUITE",
        help="Suite(s) to run. Omit to run all.",
        choices=list(SUITES.keys()),
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available suites and exit.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point. Parse args, run selected suites, print summary.

    Input:  none
    Output: none (prints to stdout; exits with code 1 if any test fails)
    """
    args = parse_args()

    if args.list:
        print("\nAvailable suites:")
        for name, scenarios in SUITES.items():
            print(f"  {name:<22} {len(scenarios)} tests")
        return

    selected = args.suite if args.suite else list(SUITES.keys())

    print(f"\nHaven Navigator Test Harness")
    print(f"Model : {config.NAVIGATOR_MODEL}")
    print(f"Map   : {len(INDEX)} nodes")
    print(f"Suites: {', '.join(selected)}")

    all_results: list[tuple[str, bool, dict | None]] = []
    for suite_name in selected:
        suite_results = run_suite(suite_name, SUITES[suite_name])
        all_results.extend(suite_results)

    # Summary
    total = len(all_results)
    passed = sum(1 for _, ok, _ in all_results if ok)
    failed = total - passed
    failed_names = [name for name, ok, _ in all_results if not ok]

    print(f"\n{SEP}")
    print(f"  Results: {passed} passed, {failed} failed ({total} total)")
    if failed_names:
        print(f"  Failed : {', '.join(failed_names)}")
    print(SEP)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
