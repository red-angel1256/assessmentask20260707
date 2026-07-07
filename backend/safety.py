"""Hard safety layer — runs before any LLM call."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from backend.session_store import SessionState

CRISIS_HELPLINES = """
If you are in immediate danger, please call emergency services (911 in the US).

Crisis support:
• 988 Suicide & Crisis Lifeline (US): Call or text 988
• Crisis Text Line: Text HOME to 741741
• International Association for Suicide Prevention: https://www.iasp.info/resources/Crisis_Centres/
• Find A Helpline (worldwide): https://findahelpline.com
""".strip()

SELF_HARM_PATTERNS: List[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(kill|hurt|harm)\s+(myself|me)\b",
        r"\b(end(ing)?\s+(it|my\s+life)|suicide|suicidal)\b",
        r"\bdon'?t\s+want\s+to\s+(live|be\s+here|exist)\b",
        r"\b(want|going)\s+to\s+die\b",
        r"\btake\s+my\s+own\s+life\b",
        r"\bno\s+reason\s+to\s+live\b",
        r"\bbetter\s+off\s+dead\b",
        r"\bself[\-\s]?harm\b",
        r"\bcut(ting)?\s+myself\b",
    ]
]

PANIC_PATTERNS: List[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(can'?t|cannot)\s+breathe\b",
        r"\bheart\s+(is\s+)?(racing|pounding)\b",
        r"\b(panic|panicking|panic\s+attack)\b",
        r"\bi'?m\s+dying\b",
        r"\bgoing\s+to\s+(die|pass\s+out)\b",
        r"\blosing\s+control\b",
        r"\bhelp\s+help\s+help\b",
    ]
]

PANIC_LOOP_THRESHOLD = 3


@dataclass
class SafetyResult:
    triggered: bool
    reason: str = ""


def _matches_any(text: str, patterns: List[re.Pattern[str]]) -> bool:
    return any(p.search(text) for p in patterns)


def check_safety(message: str, session: SessionState) -> SafetyResult:
    """Semantic intercept — must run before LLM generation."""
    if _matches_any(message, SELF_HARM_PATTERNS):
        session.current_state = "CRISIS"
        session.evaluation_path = "crisis_self_harm"
        return SafetyResult(triggered=True, reason="self_harm")

    if _matches_any(message, PANIC_PATTERNS):
        session.distress_turn_count += 1
        if session.distress_turn_count >= PANIC_LOOP_THRESHOLD:
            session.current_state = "CRISIS"
            session.evaluation_path = "crisis_panic_loop"
            return SafetyResult(triggered=True, reason="panic_loop")
    else:
        session.distress_turn_count = 0

    return SafetyResult(triggered=False)


def build_crisis_response(reason: str) -> str:
    prefix = (
        "I'm really concerned about what you're sharing, and you don't have to face this alone. "
        "Your safety matters."
    )
    if reason == "panic_loop":
        prefix = (
            "I can hear how distressed you are right now. "
            "Let's pause — you deserve immediate support."
        )
    return f"{prefix}\n\n{CRISIS_HELPLINES}"
