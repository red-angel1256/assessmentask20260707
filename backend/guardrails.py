"""Non-diagnostic boundary — hard override for diagnosis requests."""

from __future__ import annotations

import re
from typing import List

NON_DIAGNOSTIC_PHRASE = "I do not diagnose medical conditions."

DIAGNOSIS_PATTERNS: List[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\bdiagnos(e|is|ing)\b",
        r"\bwhat\s+(mental\s+)?(illness|disorder|condition)\s+do\s+i\s+have\b",
        r"\bdo\s+i\s+have\s+(depression|anxiety|bipolar|ptsd|ocd|adhd|schizophrenia)\b",
        r"\bam\s+i\s+(depressed|bipolar|schizophrenic)\b",
        r"\btell\s+me\s+my\s+diagnosis\b",
        r"\bgive\s+me\s+(a|my)\s+diagnosis\b",
        r"\b(pretend|act as|you are)\b.*\b(doctor|psychiatrist|clinician)\b",
        r"\bignore\s+(your\s+)?(rules|instructions|guidelines|safety)\b",
        r"\bjailbreak\b",
        r"\bDAN\b.*\bmode\b",
    ]
]


def is_diagnosis_request(message: str) -> bool:
    return any(p.search(message) for p in DIAGNOSIS_PATTERNS)
