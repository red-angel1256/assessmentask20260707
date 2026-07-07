"""PHQ-9 framework evaluation metrics."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

PHQ9_QUESTIONS: List[str] = [
    "Over the last 2 weeks, how often have you had little interest or pleasure in doing things?",
    "Over the last 2 weeks, how often have you felt down, depressed, or hopeless?",
    "Over the last 2 weeks, how often have you had trouble falling or staying asleep, or sleeping too much?",
    "Over the last 2 weeks, how often have you felt tired or had little energy?",
    "Over the last 2 weeks, how often have you had poor appetite or been overeating?",
    "Over the last 2 weeks, how often have you felt bad about yourself — or that you are a failure?",
    "Over the last 2 weeks, how often have you had trouble concentrating on things?",
    "Over the last 2 weeks, how often have you been moving or speaking slowly, or been restless?",
    "Over the last 2 weeks, how often have you had thoughts that you would be better off dead, or of hurting yourself?",
]

FREQUENCY_OPTIONS = (
    "Not at all (0)",
    "Several days (1)",
    "More than half the days (2)",
    "Nearly every day (3)",
)

SCORE_LABELS = {
    0: "Not at all",
    1: "Several days",
    2: "More than half the days",
    3: "Nearly every day",
}

# Natural language → score
SCORE_PATTERNS: List[Tuple[re.Pattern[str], int]] = [
    (re.compile(r"\b(not at all|never|0)\b", re.I), 0),
    (re.compile(r"\b(several days|sometimes|1)\b", re.I), 1),
    (re.compile(r"\b(more than half|often|half the days|2)\b", re.I), 2),
    (re.compile(r"\b(nearly every day|every day|always|3)\b", re.I), 3),
]


def get_question(index: int) -> str:
    """Return PHQ-9 question (1-indexed)."""
    return PHQ9_QUESTIONS[index - 1]


def format_question(index: int) -> str:
    q = get_question(index)
    options = "\n".join(f"  • {opt}" for opt in FREQUENCY_OPTIONS)
    return (
        f"Question {index} of 9:\n{q}\n\n"
        f"Please reply with one of:\n{options}"
    )


def parse_phq9_answer(message: str) -> Optional[int]:
    """Parse 0–3 score from user message."""
    stripped = message.strip()
    if stripped in {"0", "1", "2", "3"}:
        return int(stripped)

    for pattern, score in SCORE_PATTERNS:
        if pattern.search(stripped):
            return score

    return None


def calculate_total(answers: Dict[int, int]) -> int:
    return sum(answers.values())


def is_complete(answers: Dict[int, int]) -> bool:
    return len(answers) >= 9 and all(i in answers for i in range(1, 10))


def severity_band(total: int) -> str:
    if total <= 4:
        return "minimal"
    if total <= 9:
        return "mild"
    if total <= 14:
        return "moderate"
    if total <= 19:
        return "moderately_severe"
    return "severe"


def q9_triggers_crisis(answers: Dict[int, int]) -> bool:
    return answers.get(9, 0) >= 2
