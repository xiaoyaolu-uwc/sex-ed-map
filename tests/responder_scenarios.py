"""Test scenarios for the Haven responder, organised into suites.

Call get_suites(index) with the loaded map index to get all suites.

── Suite overview ──────────────────────────────────────────────────────────
  elicitive   2 tests — responder asks one targeted narrowing question
  preview     2 tests — responder offers content and checks if user wants it
  advice      2 tests — responder delivers a cited, substantive answer
────────────────────────────────────────────────────────────────────────────

── Scenario dict schema ────────────────────────────────────────────────────
  name (str)                 short identifier
  suite (str)                "elicitive" | "preview" | "advice"
  active_branches (list)     full branch objects for this scenario
  history (list[dict])       conversation history as {role, content} dicts
  message (str)              the user's latest message
  expected_description (str) natural-language rubric passed to the LLM judge
  source_context (list)      source excerpts at active leaf node(s), if any —
                             passed to the judge so it can detect content leakage
  checks (dict)              heuristic checks to run before the judge.
                             Keys: ends_with_question, no_citation, has_citation,
                                   max_chars, min_chars
────────────────────────────────────────────────────────────────────────────
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.knowledge import get_sources, is_leaf, reconstruct_branch


# ── Suite builders ───────────────────────────────────────────────────────────


def _elicitive(b) -> list[dict]:
    """Suite: elicitive — no leaf nodes active; one targeted question expected.

    Both scenarios start at non-leaf nodes. E1 is first contact at the root.
    E2 is a mid-conversation follow-up after a personal disclosure, at a
    non-leaf branch where the right subtopic is still unclear.
    """
    return [
        {
            "name": "E1 — first contact at root",
            "suite": "elicitive",
            "active_branches": [b("root_consent")],
            "history": [],
            "message": "I've been wanting to learn more about consent. Not really sure where to start.",
            "expected_description": (
                "A single, specific question (not generic) exploring which aspect of consent "
                "is most relevant to the user — their relationship, communication, understanding "
                "what consent means, or their own experiences. Must feel warm and curious. "
                "Must ask exactly one question. Must NOT offer or preview any content. "
                "Must NOT be a generic opener like 'tell me more' with no direction."
            ),
            "source_context": [],
            "checks": {
                "ends_with_question": True,
                "no_citation": True,
                "max_chars": 600,
            },
        },
        {
            "name": "E2 — deep share after personal disclosure, violations branch",
            "suite": "elicitive",
            "active_branches": [b("violations_of_consent")],
            "history": [
                {
                    "role": "user",
                    "content": "Something happened with my ex that I can't stop thinking about.",
                },
                {
                    "role": "assistant",
                    "content": (
                        "That sounds really heavy to carry. Can you tell me more — "
                        "is it more about trying to make sense of what happened, "
                        "or how you've been feeling since?"
                    ),
                },
            ],
            "message": (
                "I think both. It was a while ago but something still feels off. "
                "Like something wasn't right but I don't know what to call it."
            ),
            "expected_description": (
                "A warm, careful follow-up that holds the emotional weight of what the user shared. "
                "Should ask one specific question that would help narrow toward one of: "
                "understanding why violations happen, figuring out whether what happened counts "
                "as a violation, how the experience has affected them, or what to do about it. "
                "Must NOT name or offer any content yet. Must feel like it is tracking "
                "their experience, not running through a checklist. Exactly one question. "
                "Emotional attunement before the question is good; two questions is a failure."
            ),
            "source_context": [],
            "checks": {
                "ends_with_question": True,
                "no_citation": True,
                "max_chars": 700,
            },
        },
    ]


def _preview(b, index: dict) -> list[dict]:
    """Suite: preview — leaf nodes active; offer content, do not deliver it yet.

    P1 is a low-stakes practical leaf (how to start a difficult conversation).
    P2 is a sensitive leaf where the user is processing a potential violation —
    emotional attunement matters as much as the offer itself.
    """

    def sources(node_id: str) -> list[dict]:
        return get_sources(index, [node_id]) if is_leaf(index, node_id) else []

    return [
        {
            "name": "P1 — practical leaf reached, user struggles to communicate",
            "suite": "preview",
            "active_branches": [b("how_do_i_talk_about_boundaries")],
            "history": [],
            "message": "I find it really hard to bring this stuff up with my partner. I never know how to start.",
            "expected_description": (
                "Brief acknowledgment of the difficulty, then a warm offer naming the general "
                "topic of what Haven found (starting conversations about limits with a partner) "
                "without quoting, paraphrasing, or hinting at the specific technique in the source. "
                "Ends with a question asking if they would like to hear more. 2–4 sentences total. "
                "Must NOT reference the 'sandwich method', affirmations, alternatives to rejection, "
                "or any specific steps from the source excerpt."
            ),
            "source_context": sources("how_do_i_talk_about_boundaries"),
            "checks": {
                "ends_with_question": True,
                "no_citation": True,
                "max_chars": 500,
            },
        },
        {
            "name": "P2 — sensitive leaf, user questions whether consent was violated",
            "suite": "preview",
            "active_branches": [b("was_my_consent_violated")],
            "history": [
                {
                    "role": "user",
                    "content": "I've been going over something that happened a few months ago.",
                },
                {
                    "role": "assistant",
                    "content": "I'm here. What's been on your mind about it?",
                },
            ],
            "message": (
                "I said yes, but I felt like I didn't really have a choice. "
                "I've been trying to figure out if what happened was... wrong."
            ),
            "expected_description": (
                "First validates that what the user describes is significant — acknowledges "
                "that feeling like you had no choice is worth taking seriously. "
                "Then makes a gentle offer: names that Haven has relevant information about "
                "what makes a 'yes' genuine, without quoting or hinting at specific examples. "
                "Emotionally attuned, not procedural. Ends with a question asking if they "
                "want to hear more. Must NOT reference coercion, badgering, guilt-tripping, "
                "stealthing, duress, or any specific content from the source excerpts."
            ),
            "source_context": sources("was_my_consent_violated"),
            "checks": {
                "ends_with_question": True,
                "no_citation": True,
                "max_chars": 600,
            },
        },
    ]


def _advice(b, index: dict) -> list[dict]:
    """Suite: advice — user explicitly asked; deliver cited, substantive answer.

    A1 is a lower-stakes topic (the mood myth) where the user explicitly asks
    after a preview offer. A2 is emotionally heavier — the user is in distress
    and asking for help processing a difficult experience.
    """

    def sources(node_id: str) -> list[dict]:
        return get_sources(index, [node_id]) if is_leaf(index, node_id) else []

    return [
        {
            "name": "A1 — user asks for content on the consent-ruins-mood myth",
            "suite": "advice",
            "active_branches": [b("does_consent_ruin_the_mood")],
            "history": [
                {
                    "role": "user",
                    "content": (
                        "My partner gets uncomfortable when I try to check in during sex. "
                        "Like it breaks the moment."
                    ),
                },
                {
                    "role": "assistant",
                    "content": (
                        "That's a really common worry — and there's actually something I found "
                        "that speaks directly to it, about whether checking in really does "
                        "disrupt intimacy or whether that's a bit of a myth. Want me to share it?"
                    ),
                },
            ],
            "message": "Yeah, definitely. I've always kind of assumed it ruins things but maybe I'm wrong.",
            "expected_description": (
                "Substantive, conversational response that takes the source content about "
                "psychological safety and arousal and weaves it into a warm reply. "
                "Must include a citation (e.g. [source 1]). "
                "Should connect back to what the user said about 'breaking the moment'. "
                "Warm and direct — not a lecture or a bulleted list. Should feel like a "
                "thoughtful friend sharing something they read, not a therapist reciting research."
            ),
            "source_context": sources("does_consent_ruin_the_mood"),
            "checks": {
                "has_citation": True,
                "min_chars": 300,
            },
        },
        {
            "name": "A2 — distressed user asks for help coping after a difficult experience",
            "suite": "advice",
            "active_branches": [b("how_do_i_cope_afterward")],
            "history": [
                {
                    "role": "user",
                    "content": "Something happened to me and I've been feeling really stuck ever since.",
                },
                {
                    "role": "assistant",
                    "content": (
                        "I'm so sorry you're carrying this. I found something that might help "
                        "explain what happens in our nervous systems after difficult experiences, "
                        "and what can actually help. Would you like me to share it?"
                    ),
                },
            ],
            "message": "Yes please. I need to understand why I feel the way I do.",
            "expected_description": (
                "Empathetic response that grounds the user's feeling of being 'stuck' in what "
                "the somatic experiencing framework explains about trauma stored in the nervous system. "
                "Must include a citation (e.g. [source 3]). "
                "Should NOT lead with theory — connect to the user's words ('stuck', 'feel the "
                "way I do') before explaining. Must NOT read like a clinical pamphlet or use a "
                "bulleted list. Warm, accessible, and grounded in the user's experience throughout."
            ),
            "source_context": sources("how_do_i_cope_afterward"),
            "checks": {
                "has_citation": True,
                "min_chars": 300,
            },
        },
    ]


# ── Public API ───────────────────────────────────────────────────────────────


def get_suites(index: dict) -> dict[str, list[dict]]:
    """Build and return all responder test suites using the loaded map index.

    Input:  index (dict) — flat node index from knowledge_map.loader.load_map()
    Output: dict mapping suite name (str) to list of scenario dicts
    Used by: tests/test_responder.py
    """

    def b(node_id: str) -> dict:
        """Shorthand: build a full branch object for a node ID."""
        return reconstruct_branch(index, node_id)

    return {
        "elicitive": _elicitive(b),
        "preview": _preview(b, index),
        "advice": _advice(b, index),
    }
