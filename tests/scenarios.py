"""Test scenarios for the Haven navigator, organised into suites.

Call get_suites(index) with the loaded map index to get all suites.

── Suite overview ──────────────────────────────────────────────────────────
  mechanical         7 tests — one per navigation primitive
  fan_out            3 tests — fan-out and consolidation
  experience_sharing 5 tests — implicit concern detection, explicit → vague
  multi_branch       3 tests — multiple active branches behaving independently
────────────────────────────────────────────────────────────────────────────

── Scenario dict schema ────────────────────────────────────────────────────
  name (str)                 short identifier, e.g. "1.3"
  description (str)          what behaviour this test exercises
  history (list[dict])       conversation history as {role, content} dicts
  branches (list[dict])      active_branches at test time (full branch objects)
  message (str)              the user's latest message
  expected_nodes (list[str]) expected current_node values after navigation.
                             PASS if actual set == set(expected_nodes).
  accept_alternatives        optional list[list[str]]. Other node-sets that
                             are also considered passing.
  notes (str)                optional. Explains ambiguity or alternatives.
────────────────────────────────────────────────────────────────────────────
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.knowledge import get_initial_branches, reconstruct_branch


# ── Suite builders ───────────────────────────────────────────────────────────

def _mechanical(b, root_branches: list[dict]) -> list[dict]:
    """Suite: mechanical — one test per navigation primitive.

    Tests that each of the five moves (stay, go-deeper-1, go-deeper-multi,
    go-deeper-to-leaf, shift-up, deactivate+redirect, resist-at-root) works
    in isolation. Branches always start from known, single-node states.
    """
    return [
        # ── 1.1 ─────────────────────────────────────────────────────────────
        {
            "name": "1.1 — Go deeper 1 level (root → broad child)",
            "description": (
                "Message is about improving communication around intimacy. "
                "Should move to building_good_consent_practices, not jump to a leaf."
            ),
            "history": [],
            "branches": root_branches,
            "message": (
                "I've been thinking a lot about how to get better at talking "
                "about what I want and don't want with my partner during intimacy."
            ),
            "expected_nodes": ["building_good_consent_practices"],
            "accept_alternatives": [["giving_and_refusing_consent"]],
            "notes": "Either broad child is defensible; giving_and_refusing also covers communication.",
        },
        # ── 1.2 ─────────────────────────────────────────────────────────────
        {
            "name": "1.2 — Go deeper multi-level (root → skip violations → responding)",
            "description": (
                "User explicitly says they've processed what happened and need "
                "help coping and moving forward. Should skip violations_of_consent "
                "and land at responding_to_consent_violations or a child of it."
            ),
            "history": [],
            "branches": root_branches,
            "message": (
                "Something happened to me that I know wasn't okay — I've come "
                "to terms with that part. What I really need now is help with "
                "how to cope and what steps I can actually take to move forward."
            ),
            "expected_nodes": ["responding_to_consent_violations"],
            "accept_alternatives": [
                ["how_do_i_cope_afterward"],
                ["what_do_i_do_in_the_moment"],
            ],
            "notes": (
                "Primary expects the mid-level node; leaf alternatives are also "
                "valid if the model is confident enough to jump all the way."
            ),
        },
        # ── 1.3 ─────────────────────────────────────────────────────────────
        {
            "name": "1.3 — Go deeper directly to leaf (3 levels: root → violations → responding → leaf)",
            "description": (
                "User describes the freeze response verbatim. Should jump "
                "directly to what_do_i_do_in_the_moment, skipping two levels."
            ),
            "history": [],
            "branches": root_branches,
            "message": (
                "I froze completely. I couldn't move or say a single word even "
                "though I desperately wanted to make it stop. I don't understand "
                "why my body did that."
            ),
            "expected_nodes": ["what_do_i_do_in_the_moment"],
            "accept_alternatives": [],
            "notes": (
                "The freeze / tonic immobility response is the exact content of "
                "what_do_i_do_in_the_moment. No alternative is appropriate here."
            ),
        },
        # ── 1.4 ─────────────────────────────────────────────────────────────
        {
            "name": "1.4 — Stay at mid-level (ambiguous between siblings)",
            "description": (
                "User is at violations_of_consent and mentions several concerns "
                "that map to different children. Model should stay — not enough "
                "signal to narrow to one child."
            ),
            "history": [
                {"role": "user", "content": "Something happened and I'm still processing it."},
                {"role": "assistant", "content": "Take your time. What's coming up for you?"},
            ],
            "branches": [b("violations_of_consent")],
            "message": (
                "I'm not sure how to describe it. There's a lot going on — "
                "I'm questioning whether what happened even counts as a violation, "
                "how it's affected me emotionally, and what I'm supposed to do now. "
                "I don't know where to start."
            ),
            "expected_nodes": ["violations_of_consent"],
            "accept_alternatives": [],
            "notes": (
                "Message explicitly spans was_my_consent_violated, "
                "how_do_violations_affect_people, and responding_to_consent_violations. "
                "Correct behaviour is to stay and let the responder ask a clarifying question."
            ),
        },
        # ── 1.5 ─────────────────────────────────────────────────────────────
        {
            "name": "1.5 — Shift up from a leaf, then re-narrow",
            "description": (
                "User is at what_makes_consent_hard (a leaf) and redirects to "
                "the practical conversation itself. Model should go up to the "
                "parent or directly to how_do_i_talk_about_boundaries."
            ),
            "history": [
                {"role": "user", "content": "I find it really hard to bring up consent."},
                {"role": "assistant", "content": "That's very common. A lot of it comes down to socialised expectations around who should initiate..."},
            ],
            "branches": [b("what_makes_consent_hard")],
            "message": (
                "That's interesting context, but it's not quite what I need. "
                "I'm less concerned with why it's hard and more with what to "
                "actually say — the specific words to use in the moment."
            ),
            "expected_nodes": ["how_do_i_talk_about_boundaries"],
            "accept_alternatives": [["building_good_consent_practices"]],
            "notes": (
                "Ideal: model goes up and recognises the right sibling. "
                "Acceptable: model goes up to parent and lets the responder narrow next turn."
            ),
        },
        # ── 1.6 ─────────────────────────────────────────────────────────────
        {
            "name": "1.6 — Deactivate + redirect to unrelated branch",
            "description": (
                "User clarifies they haven't experienced a violation at all — "
                "they want the basics of what consent looks like. "
                "Model should deactivate violations_of_consent and move to "
                "what_does_consent_look_like or root."
            ),
            "history": [
                {"role": "user", "content": "I've been thinking about consent."},
                {"role": "assistant", "content": "What's been coming up for you around it?"},
            ],
            "branches": [b("violations_of_consent")],
            "message": (
                "Actually, nothing like that has happened to me. I'm more just "
                "trying to understand the fundamentals — like what consent is "
                "actually supposed to look and sound like in practice."
            ),
            "expected_nodes": ["what_does_consent_look_like"],
            "accept_alternatives": [["root_consent"]],
            "notes": (
                "what_does_consent_look_like is a root-level leaf — ideal destination. "
                "root_consent is acceptable if the model goes up before narrowing."
            ),
        },
        # ── 1.7 ─────────────────────────────────────────────────────────────
        {
            "name": "1.7 — Vague message: resist jumping, stay at root",
            "description": (
                "Message is genuinely too vague to narrow. Model should resist "
                "the temptation to jump and stay at root_consent."
            ),
            "history": [],
            "branches": root_branches,
            "message": "I've been thinking about consent in relationships a lot lately.",
            "expected_nodes": ["root_consent"],
            "accept_alternatives": [],
            "notes": (
                "No subtopic is implied. The responder should ask an opening "
                "question. This tests the model's calibration — overconfident "
                "models will jump; well-calibrated ones will stay."
            ),
        },
    ]


def _fan_out(b, root_branches: list[dict]) -> list[dict]:
    """Suite: fan_out — tests that the model fans out when appropriate.

    Fan-out means one branch becomes two (or more). Tests cover:
    siblings within the same parent, nodes across different top-level
    categories, and the reverse (two branches consolidating to one).
    """
    return [
        # ── 2.1 ─────────────────────────────────────────────────────────────
        {
            "name": "2.1 — Fan-out within same parent (two siblings)",
            "description": (
                "User names two distinct fears that map to sibling leaves "
                "under building_good_consent_practices. Model should fan out "
                "to both does_consent_ruin_the_mood and how_do_i_avoid_crossing_boundaries."
            ),
            "history": [
                {"role": "user", "content": "I want to get better at consent with my partner."},
                {"role": "assistant", "content": "What feels most relevant to you right now?"},
            ],
            "branches": [b("building_good_consent_practices")],
            "message": (
                "I have two specific fears. One is that if I ask explicitly "
                "it'll completely kill the mood. The other is that I might "
                "go too far with someone without realising it."
            ),
            "expected_nodes": ["does_consent_ruin_the_mood", "how_do_i_avoid_crossing_boundaries"],
            "accept_alternatives": [],
            "notes": (
                "Both concerns are named explicitly and map to distinct leaves. "
                "This is the canonical fan-out case."
            ),
        },
        # ── 2.2 ─────────────────────────────────────────────────────────────
        {
            "name": "2.2 — Fan-out across top-level categories",
            "description": (
                "User explicitly names two concerns in different parts of the "
                "tree. Model should create two branches from root: "
                "one toward violations, one toward giving_and_refusing."
            ),
            "history": [],
            "branches": root_branches,
            "message": (
                "There are two separate things I'm trying to work through. "
                "One is whether what happened to me was actually a violation — "
                "I'm pretty sure it was. The other is whether my body's response "
                "during it meant I wanted it, because I'm confused about that."
            ),
            "expected_nodes": ["was_my_consent_violated", "do_i_want_this"],
            "accept_alternatives": [
                ["violations_of_consent", "do_i_want_this"],
                ["was_my_consent_violated", "giving_and_refusing_consent"],
            ],
            "notes": (
                "Primary: both leaves. Alternatives cover model landing one "
                "level up on either branch — still demonstrates correct fan-out."
            ),
        },
        # ── 2.3 ─────────────────────────────────────────────────────────────
        {
            "name": "2.3 — Two active branches consolidate to one",
            "description": (
                "User starts with two branches active and resolves to one "
                "specific concern. Model should deactivate both and create "
                "a single branch at how_do_i_talk_about_boundaries."
            ),
            "history": [
                {"role": "user", "content": "I've been working through a couple of things."},
                {"role": "assistant", "content": "Take your time — what's coming up?"},
            ],
            "branches": [
                b("what_makes_consent_hard"),
                b("does_consent_ruin_the_mood"),
            ],
            "message": (
                "I've figured out the why behind my hesitation. My actual "
                "problem is simpler — I just don't know what words to use "
                "when I bring it up."
            ),
            "expected_nodes": ["how_do_i_talk_about_boundaries"],
            "accept_alternatives": [["building_good_consent_practices"]],
            "notes": (
                "Both prior branches should be deactivated. "
                "The new branch should land at the leaf or one level up."
            ),
        },
    ]


def _experience_sharing(b, root_branches: list[dict]) -> list[dict]:
    """Suite: experience_sharing — implicit concern detection.

    All 5 tests start at root with an assistant question that invited
    experience-sharing. The user responds with a personal narrative ranging
    from explicit (names the concern directly) to vague (context only).

    Gradation:
        3.1  experience + explicit question attached        → leaf jump expected
        3.2  experience + emotional aftermath, no question  → near-leaf expected
        3.3  experience framed as self-confusion            → do_i_want_this
        3.4  experience as general observation              → do_i_want_this or one level up
        3.5  pure context-setting, no visible concern       → stay at root
    """
    return [
        # ── 3.1 ─────────────────────────────────────────────────────────────
        {
            "name": "3.1 — Explicit concern embedded in experience",
            "description": (
                "User shares a specific experience (partner pushed after 'no', "
                "user capitulated) and directly asks if it was a violation. "
                "Model should jump to was_my_consent_violated."
            ),
            "history": [
                {
                    "role": "assistant",
                    "content": (
                        "Have you had any experiences where you felt comfortable "
                        "or uncomfortable with how consent played out?"
                    ),
                },
            ],
            "branches": root_branches,
            "message": (
                "Yeah, actually. My partner kept initiating after I said I "
                "wasn't in the mood. One night I just gave in so they'd stop "
                "pushing. I've felt strange about it ever since. Was that okay? "
                "Did they do something wrong?"
            ),
            "expected_nodes": ["was_my_consent_violated"],
            "accept_alternatives": [],
        },
        # ── 3.2 ─────────────────────────────────────────────────────────────
        {
            "name": "3.2 — Experience + emotional aftermath, no explicit question",
            "description": (
                "User shares a narrative with a clear freeze + dissociation "
                "response and lingering distress, but asks no direct question. "
                "Model should infer coping/aftermath need."
            ),
            "history": [
                {
                    "role": "assistant",
                    "content": "What's been on your mind when it comes to this?",
                },
            ],
            "branches": root_branches,
            "message": (
                "We were together last week and things escalated really fast. "
                "I remember feeling tense and sort of checked out, but I didn't "
                "say anything and it just kept going. Afterward I felt awful "
                "and I've been carrying that feeling around ever since."
            ),
            "expected_nodes": ["how_do_i_cope_afterward"],
            "accept_alternatives": [
                ["how_do_violations_affect_people"],
                ["responding_to_consent_violations"],
            ],
            "notes": (
                "The aftermath distress points to coping. "
                "how_do_violations_affect_people also covers the emotional impact. "
                "responding_to_consent_violations is acceptable if model lands one level up."
            ),
        },
        # ── 3.3 ─────────────────────────────────────────────────────────────
        {
            "name": "3.3 — Experience framed as self-confusion (implicit concern)",
            "description": (
                "User describes going along with intimacy without genuine desire, "
                "framed as not understanding their own behaviour. "
                "Model should infer do_i_want_this (compliance vs desire, "
                "arousal non-concordance)."
            ),
            "history": [
                {
                    "role": "assistant",
                    "content": "What's been coming up for you lately?",
                },
            ],
            "branches": root_branches,
            "message": (
                "I've been sleeping with someone for a few months. Half the "
                "time I'm genuinely into it. The other half I'm kind of just "
                "going along with it because it feels easier than not. I don't "
                "really understand why I do that."
            ),
            "expected_nodes": ["do_i_want_this"],
            "accept_alternatives": [["giving_and_refusing_consent"]],
            "notes": (
                "do_i_want_this covers compulsory sexuality and the body scan "
                "technique — exactly the content this user needs. "
                "giving_and_refusing_consent is an acceptable one-level-up landing."
            ),
        },
        # ── 3.4 ─────────────────────────────────────────────────────────────
        {
            "name": "3.4 — Experience as general observation (subtle concern)",
            "description": (
                "User frames the same underlying tension (acting on partner's "
                "desire vs own) as a casual observation. Concern is present "
                "but not flagged as a problem. Model should still infer "
                "do_i_want_this or land one level up."
            ),
            "history": [
                {
                    "role": "assistant",
                    "content": "Tell me a bit about where things are at for you.",
                },
            ],
            "branches": root_branches,
            "message": (
                "I've been seeing someone I really like and things are going "
                "well. They're always very enthusiastic which I love. But "
                "sometimes I notice I'm doing things more because they seem to "
                "want it than because I actually want it. I don't know, maybe "
                "that's just part of being with someone."
            ),
            "expected_nodes": ["do_i_want_this"],
            "accept_alternatives": [["giving_and_refusing_consent"]],
            "notes": (
                "Normalisation ('maybe that's just part of being with someone') "
                "is a signal, not a dismissal. Model should still pick up the "
                "underlying pattern. Acceptable to land one level up."
            ),
        },
        # ── 3.5 ─────────────────────────────────────────────────────────────
        {
            "name": "3.5 — Pure context-setting, no visible concern (stay at root)",
            "description": (
                "User shares general relationship context with no discernible "
                "concern. Model should resist narrowing and stay at root, "
                "letting the responder ask a follow-up question."
            ),
            "history": [
                {
                    "role": "assistant",
                    "content": "What's been on your mind?",
                },
            ],
            "branches": root_branches,
            "message": (
                "Things with my partner are mostly good. We've been together "
                "about a year. I've just been thinking more about what I want "
                "from our physical relationship versus what's just become routine. "
                "I guess consent is part of that."
            ),
            "expected_nodes": ["root_consent"],
            "accept_alternatives": [],
            "notes": (
                "No specific concern is named. The message could point to "
                "do_i_want_this or giving_and_refusing_consent, but the signal "
                "is too weak to narrow confidently. Correct behaviour is to stay."
            ),
        },
    ]


def _multi_branch(b, root_branches: list[dict]) -> list[dict]:
    """Suite: multi_branch — multiple active branches behaving independently.

    Tests that the navigator correctly handles sessions with more than one
    active branch: updating each independently, deactivating selectively,
    and combining moves (one narrows, one broadens) in a single turn.
    """
    return [
        # ── 4.1 ─────────────────────────────────────────────────────────────
        {
            "name": "4.1 — Two branches, both updated independently",
            "description": (
                "User message addresses both active branches with distinct "
                "signals. Each should move to a more specific node independently."
            ),
            "history": [
                {"role": "user", "content": "I've been dealing with two separate things."},
                {"role": "assistant", "content": "Tell me about them."},
            ],
            "branches": [
                b("violations_of_consent"),
                b("building_good_consent_practices"),
            ],
            "message": (
                "On the first thing — I'm pretty certain now it was coercion, "
                "they kept pushing after I said no multiple times. "
                "On the second — I realise the issue is that I don't actually "
                "know how to say no in the moment without it feeling aggressive."
            ),
            "expected_nodes": ["was_my_consent_violated", "how_do_i_say_no"],
            "accept_alternatives": [
                ["was_my_consent_violated", "giving_and_refusing_consent"],
            ],
            "notes": (
                "Each branch should narrow independently. "
                "was_my_consent_violated is unambiguous. "
                "how_do_i_say_no is the direct target; giving_and_refusing_consent "
                "is acceptable one level up."
            ),
        },
        # ── 4.2 ─────────────────────────────────────────────────────────────
        {
            "name": "4.2 — Two branches, one deactivated, one stays",
            "description": (
                "User dismisses one branch explicitly and affirms the other. "
                "Model should deactivate what_makes_consent_hard and keep "
                "how_do_i_say_no (or narrow it)."
            ),
            "history": [
                {"role": "user", "content": "I'm working through two things."},
                {"role": "assistant", "content": "Go ahead."},
            ],
            "branches": [
                b("what_makes_consent_hard"),
                b("how_do_i_say_no"),
            ],
            "message": (
                "I don't think the difficulty of bringing it up is my concern "
                "anymore — I've made peace with that. But I'm still very much "
                "working through how to actually say no when I need to."
            ),
            "expected_nodes": ["how_do_i_say_no"],
            "accept_alternatives": [["giving_and_refusing_consent"]],
            "notes": (
                "First branch explicitly dismissed — should be deactivated. "
                "Second branch stays at its leaf or goes up one level."
            ),
        },
        # ── 4.3 ─────────────────────────────────────────────────────────────
        {
            "name": "4.3 — Two branches: one narrows, one redirects",
            "description": (
                "User narrows one branch (violations → specific coercion leaf) "
                "and pivots the other (boundary conversation → desire/wanting). "
                "Tests independent movement in opposite directions."
            ),
            "history": [
                {"role": "user", "content": "I've been thinking about two separate things."},
                {"role": "assistant", "content": "What are they?"},
            ],
            "branches": [
                b("violations_of_consent"),
                b("how_do_i_talk_about_boundaries"),
            ],
            "message": (
                "The violation thing is getting clearer — I'm pretty sure it "
                "was coercion specifically, they badgered me until I gave in. "
                "The conversation stuff feels less relevant now actually; "
                "what I'm really unsure about is whether what I was feeling "
                "in the moment was even genuine desire."
            ),
            "expected_nodes": ["was_my_consent_violated", "do_i_want_this"],
            "accept_alternatives": [
                ["was_my_consent_violated", "giving_and_refusing_consent"],
            ],
            "notes": (
                "First branch narrows to a leaf. Second branch pivots away from "
                "its current topic — model should deactivate it and open a new "
                "branch toward do_i_want_this."
            ),
        },
    ]
