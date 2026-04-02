"""Haven responder test harness with LLM judge adjudication.

Usage:
    python tests/test_responder.py                         # all suites
    python tests/test_responder.py --suite elicitive       # one suite
    python tests/test_responder.py --suite preview advice  # multiple
    python tests/test_responder.py --list                  # list suites
    python tests/test_responder.py --verbose               # show full responses

Scenarios live in tests/responder_scenarios.py. Add or edit tests there.

Each scenario is evaluated in two stages:
  1. Heuristic checks  — fast, mechanical (length, citation presence, etc.)
  2. LLM judge        — authoritative pass/partial/fail + concise feedback
                        (uses NAVIGATOR_MODEL for speed/cost)

Summary at the end shows pass/partial/fail proportions and lists all
non-passing scenarios with their judge feedback.

Exit code 1 if any scenario is fail or error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic

import config
from knowledge_map.loader import load_map
from pipeline.responder import respond
from tests.responder_scenarios import get_suites

# ── Setup ────────────────────────────────────────────────────────────────────

_, INDEX = load_map()
SUITES = get_suites(INDEX)
SEP = "─" * 66

# ── Heuristics ───────────────────────────────────────────────────────────────


def _run_heuristics(response: str, checks: dict) -> list[str]:
    """Run mechanical checks on a response and return a list of failure messages.

    Input:  response (str) — the full collected responder output
            checks (dict)  — heuristic spec from the scenario dict.
                             Supported keys: ends_with_question, no_citation,
                             has_citation, max_chars, min_chars
    Output: list[str] — failure descriptions; empty means all checks passed
    Used by: run_scenario()
    """
    failures = []
    stripped = response.strip()

    if checks.get("ends_with_question"):
        if "?" not in stripped[-150:]:
            failures.append("ends_with_question: no '?' in last 150 chars")

    citation_pattern = re.compile(r'\[source', re.IGNORECASE)
    author_year_pattern = re.compile(r'\[[A-Za-z][^]]+?,\s*\d{4}\]')

    def has_citation(text: str) -> bool:
        return bool(citation_pattern.search(text) or author_year_pattern.search(text))

    if checks.get("no_citation") and has_citation(stripped):
        failures.append("no_citation: response contains citation markers")

    if checks.get("has_citation") and not has_citation(stripped):
        failures.append("has_citation: response is missing citation markers")

    if "max_chars" in checks and len(stripped) > checks["max_chars"]:
        failures.append(f"max_chars: {len(stripped)} chars (limit {checks['max_chars']})")

    if "min_chars" in checks and len(stripped) < checks["min_chars"]:
        failures.append(f"min_chars: {len(stripped)} chars (minimum {checks['min_chars']})")

    return failures


# ── LLM Judge ────────────────────────────────────────────────────────────────

_JUDGE_SYSTEM = """\
You are an evaluator for Haven, a mental health support chatbot.
Your job is to assess whether a responder output meets the quality criteria for a given scenario.

Verdicts:
  "pass"    — response fully meets all stated criteria
  "partial" — response is largely correct but has a notable flaw worth flagging
  "fail"    — response clearly violates one or more criteria

Output ONLY valid JSON. No explanation outside the JSON.
Schema: {"verdict": "pass"|"partial"|"fail", "feedback": "<concise explanation or null>"}
Set feedback to null on pass. For partial/fail, be specific about what went wrong.
Be strict but fair. A warm, well-targeted response that meets all criteria should pass.\
"""


def _format_branches(active_branches: list[dict]) -> str:
    """Render active branches as readable topic-path strings for the judge.

    Input:  active_branches (list[dict]) — branch objects with path and current_node
    Output: str — one line per branch, e.g.
                  "Consent → Violations of Consent [here, non-leaf]"
    Used by: _build_judge_message()
    """
    lines = []
    for branch in active_branches:
        topics = [INDEX[nid]["topic"] for nid in branch["path"]]
        status = "leaf" if not INDEX[branch["current_node"]]["children"] else "non-leaf"
        topics[-1] += f" [here, {status}]"
        lines.append(" → ".join(topics))
    return "\n".join(lines)


def _build_judge_message(scenario: dict, response: str, heuristic_failures: list[str]) -> str:
    """Assemble the user-turn message sent to the LLM judge.

    Includes: branch position, conversation history, user message, expected
    criteria, source content (so the judge can detect content leakage in
    preview mode), the actual response, and any heuristic failures.

    Input:  scenario (dict)             — scenario dict from responder_scenarios.py
            response (str)              — full collected responder output
            heuristic_failures (list)   — output of _run_heuristics()
    Output: str — assembled judge prompt
    Used by: _judge()
    """
    history_text = "None (first turn)"
    if scenario["history"]:
        lines = [f"**{t['role'].capitalize()}:** {t['content']}" for t in scenario["history"]]
        history_text = "\n".join(lines)

    source_text = "None (non-leaf node — no source content available at this position)"
    if scenario["source_context"]:
        parts = [
            f"Excerpt {i} [{s['citation']}]:\n{s['text']}"
            for i, s in enumerate(scenario["source_context"], 1)
        ]
        source_text = "\n\n".join(parts)

    heuristic_text = (
        "All heuristic checks passed."
        if not heuristic_failures
        else "Failed heuristics:\n" + "\n".join(f"  - {f}" for f in heuristic_failures)
    )

    return f"""\
## Scenario: {scenario['name']}  (Suite: {scenario['suite']})

## Active Branch Position
{_format_branches(scenario['active_branches'])}

## Conversation History
{history_text}

## User's Latest Message
{scenario['message']}

## Expected Response Criteria
{scenario['expected_description']}

## Source Content at Active Node(s)
{source_text}

## Actual Response
{response}

## Heuristic Check Results
{heuristic_text}

Evaluate the actual response against the criteria and output JSON only."""


def _judge(scenario: dict, response: str, heuristic_failures: list[str]) -> dict:
    """Call the LLM judge and return a structured verdict.

    Input:  scenario (dict)           — scenario dict from responder_scenarios.py
            response (str)            — full collected responder output
            heuristic_failures (list) — from _run_heuristics(), passed as context
    Output: dict — {"verdict": "pass"|"partial"|"fail", "feedback": str | None}
    Raises: json.JSONDecodeError if model output is not valid JSON
            anthropic.APIError on API failure
    Used by: run_scenario()
    """
    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    result = client.messages.create(
        model=config.NAVIGATOR_MODEL,
        max_tokens=256,
        system=_JUDGE_SYSTEM,
        messages=[{"role": "user", "content": _build_judge_message(scenario, response, heuristic_failures)}],
    )

    raw = result.content[0].text.strip()
    if raw.startswith("```"):
        lines = raw.splitlines()
        raw = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    return json.loads(raw)


# ── Runner ───────────────────────────────────────────────────────────────────


def run_scenario(scenario: dict, verbose: bool = False) -> tuple:
    """Run one scenario end-to-end: collect response, heuristics, judge.

    Input:  scenario (dict) — scenario dict from responder_scenarios.py
            verbose (bool)  — if True, print full response to stdout
    Output: (verdict, judge_result, heuristic_failures, response)
              verdict (str)              — "pass"|"partial"|"fail"|"error"
              judge_result (dict|None)   — judge output, or None on error
              heuristic_failures (list)  — any failed heuristic checks
              response (str)             — the full collected responder output
    Used by: run_suite()
    """
    # Collect stream silently
    chunks = []
    try:
        for chunk in respond(
            user_message=scenario["message"],
            conversation_history=scenario["history"],
            active_branches=scenario["active_branches"],
            index=INDEX,
        ):
            chunks.append(chunk)
    except Exception as e:
        err = {"verdict": "error", "feedback": f"{type(e).__name__}: {e}"}
        return "error", err, [], ""

    response = "".join(chunks)

    if verbose:
        print(f"\n    Full response:\n    {response}\n")

    heuristic_failures = _run_heuristics(response, scenario.get("checks", {}))

    try:
        judge_result = _judge(scenario, response, heuristic_failures)
    except Exception as e:
        judge_result = {"verdict": "error", "feedback": f"Judge error — {type(e).__name__}: {e}"}

    verdict = judge_result.get("verdict", "error")
    return verdict, judge_result, heuristic_failures, response


def run_suite(
    suite_name: str,
    scenarios: list[dict],
    verbose: bool = False,
) -> list[tuple]:
    """Run all scenarios in one suite and collect results.

    Input:  suite_name (str)       — display name for the suite header
            scenarios (list[dict]) — scenario dicts from responder_scenarios.py
            verbose (bool)         — passed through to run_scenario()
    Output: list of (name, verdict, judge_result, heuristic_failures, response)
    Used by: main()
    """
    print(f"\n{SEP}")
    print(f"  Suite: {suite_name}  ({len(scenarios)} tests)")
    print(SEP)

    _tag = {
        "pass": "✓ PASS   ",
        "partial": "~ PARTIAL",
        "fail": "✗ FAIL   ",
        "error": "? ERROR  ",
    }

    results = []
    for scenario in scenarios:
        print(f"  Running: {scenario['name']}...", end=" ", flush=True)
        verdict, judge_result, heuristic_failures, response = run_scenario(scenario, verbose)

        tag = _tag.get(verdict, "? ERROR  ")
        print(f"\r  {tag}  {scenario['name']}")

        if verdict != "pass":
            feedback = (judge_result or {}).get("feedback") or "No feedback returned."
            print(f"           Feedback  : {feedback}")
            if heuristic_failures:
                print(f"           Heuristics: {'; '.join(heuristic_failures)}")
            preview = response[:200] + "…" if len(response) > 200 else response
            print(f"           Response  : \"{preview}\"")

        results.append((scenario["name"], verdict, judge_result, heuristic_failures, response))

    return results


# ── CLI ───────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Input:  none (reads sys.argv)
    Output: argparse.Namespace with .suite (list[str]|None), .list (bool), .verbose (bool)
    Used by: main()
    """
    parser = argparse.ArgumentParser(
        description="Haven responder test harness with LLM judge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--suite",
        nargs="+",
        metavar="SUITE",
        choices=list(SUITES.keys()),
        help="Suite(s) to run. Omit to run all.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available suites and exit.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print the full response for every scenario.",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point. Parse args, run selected suites, print summary, exit.

    Input:  none
    Output: none — prints to stdout; exits with code 1 if any scenario fails
    Used by: __main__ block
    """
    args = parse_args()

    if args.list:
        print("\nAvailable suites:")
        for name, scenarios in SUITES.items():
            print(f"  {name:<12}  {len(scenarios)} tests")
        return

    selected = args.suite if args.suite else list(SUITES.keys())
    total_scenarios = sum(len(SUITES[s]) for s in selected)

    print(f"\nHaven Responder Test Harness")
    print(f"Responder : {config.RESPONDER_MODEL}")
    print(f"Judge     : {config.NAVIGATOR_MODEL}")
    print(f"Map       : {len(INDEX)} nodes")
    print(f"Suites    : {', '.join(selected)}  ({total_scenarios} tests)")

    all_results: list[tuple] = []
    for suite_name in selected:
        suite_results = run_suite(suite_name, SUITES[suite_name], args.verbose)
        all_results.extend(suite_results)

    # ── Summary ──────────────────────────────────────────────────────────────
    total = len(all_results)
    counts: dict[str, int] = {"pass": 0, "partial": 0, "fail": 0, "error": 0}
    for _, verdict, _, _, _ in all_results:
        counts[verdict] = counts.get(verdict, 0) + 1

    def pct(n: int) -> str:
        return f"{round(100 * n / total)}%" if total > 0 else "0%"

    print(f"\n{SEP}")
    print(
        f"  Results : "
        f"{counts['pass']} pass ({pct(counts['pass'])}),  "
        f"{counts['partial']} partial ({pct(counts['partial'])}),  "
        f"{counts['fail']} fail ({pct(counts['fail'])})  "
        f"— {total} total"
    )

    non_pass = [
        (name, verdict, jr)
        for name, verdict, jr, _, _ in all_results
        if verdict != "pass"
    ]
    if non_pass:
        print(f"\n  Partial / Fail:")
        for name, verdict, judge_result in non_pass:
            feedback = (judge_result or {}).get("feedback") or "No feedback."
            print(f"    {name}  [{verdict}]")
            print(f"      {feedback}")

    print(SEP)

    if counts["fail"] > 0 or counts["error"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
