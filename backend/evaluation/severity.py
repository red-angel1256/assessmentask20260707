"""Dynamic psychological severity index and DSM-5-aligned cognitive profiling."""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from backend.evaluation.phq9 import calculate_total, severity_band
from backend.session_store import SessionState

# DSM-5-aligned cognitive domain keyword signals (profiling, not diagnosis)
DOMAIN_KEYWORDS: Dict[str, List[Tuple[re.Pattern[str], float]]] = {
    "mood": [
        (re.compile(r"\b(hopeless|sad|depressed|empty|numb|down)\b", re.I), 0.3),
        (re.compile(r"\b(no interest|anhedonia|no pleasure)\b", re.I), 0.25),
    ],
    "anxiety": [
        (re.compile(r"\b(worried|anxious|nervous|on edge)\b", re.I), 0.3),
        (re.compile(r"\b(panic|panic attack|heart racing)\b", re.I), 0.35),
    ],
    "cognition": [
        (re.compile(r"\b(can'?t focus|concentrat|forgetful|brain fog)\b", re.I), 0.3),
        (re.compile(r"\b(decision|thinking clearly)\b", re.I), 0.2),
    ],
    "behavior": [
        (re.compile(r"\b(withdraw|isolat|avoid|staying in bed)\b", re.I), 0.3),
        (re.compile(r"\b(no energy|can'?t get out)\b", re.I), 0.25),
    ],
    "self_concept": [
        (re.compile(r"\b(worthless|failure|guilty|self[\-\s]?hatred)\b", re.I), 0.35),
        (re.compile(r"\b(bad about myself|let everyone down)\b", re.I), 0.3),
    ],
}

CRISIS_PROXIMITY_PATTERNS = [
    re.compile(r"\b(don'?t want to live|give up|can'?t go on)\b", re.I),
    re.compile(r"\b(hurt myself|better off dead)\b", re.I),
]

SEVERITY_ESCALATION_THRESHOLD = 0.55
DSM_DOMAIN_SPIKE_THRESHOLD = 0.5
DSM_ESCALATION_DOMAINS = ("mood", "self_concept")


def update_dsm5_domains(session: SessionState, message: str) -> None:
    """Update cognitive domain scores from free-text signals."""
    for domain, patterns in DOMAIN_KEYWORDS.items():
        current = session.dsm5_domains.get(domain, 0.0)
        for pattern, weight in patterns:
            if pattern.search(message):
                current = min(1.0, current + weight)
        session.dsm5_domains[domain] = round(current, 3)


def _crisis_proximity_boost(message: str) -> float:
    if any(p.search(message) for p in CRISIS_PROXIMITY_PATTERNS):
        return 0.15
    return 0.0


def _session_trend(session: SessionState) -> float:
    """Slight boost if severity has been building across turns."""
    if session.turn_count >= 5 and session.severity_index > 0.3:
        return 0.05
    return 0.0


def get_dsm5_snapshot(session: SessionState) -> Dict[str, float]:
    """Return all DSM-5-aligned domain scores (defaults to 0.0)."""
    return {name: session.dsm5_domains.get(name, 0.0) for name in DOMAIN_KEYWORDS}


def should_escalate(session: SessionState) -> bool:
    """True when severity index or DSM-5 mood/self-concept domains warrant escalation."""
    if session.severity_index >= SEVERITY_ESCALATION_THRESHOLD:
        return True
    return any(
        session.dsm5_domains.get(domain, 0.0) >= DSM_DOMAIN_SPIKE_THRESHOLD
        for domain in DSM_ESCALATION_DOMAINS
    )


def escalation_reason(session: SessionState) -> str:
    """Describe why dynamic routing chose escalation."""
    if session.severity_index >= SEVERITY_ESCALATION_THRESHOLD:
        return "severity_index"
    for domain in DSM_ESCALATION_DOMAINS:
        if session.dsm5_domains.get(domain, 0.0) >= DSM_DOMAIN_SPIKE_THRESHOLD:
            return f"dsm5_{domain}_spike"
    return "severity_index"


def recalculate_severity(session: SessionState, message: str) -> None:
    """Recalculate dynamic severity index on every turn."""
    update_dsm5_domains(session, message)

    phq9_total = calculate_total(session.phq9_answers)
    phq9_normalized = phq9_total / 27.0 if session.phq9_answers else 0.0

    domain_scores = list(session.dsm5_domains.values())
    domain_max = max(domain_scores) if domain_scores else 0.0
    domain_avg = sum(domain_scores) / len(domain_scores) if domain_scores else 0.0

    crisis_boost = _crisis_proximity_boost(message)
    trend_boost = _session_trend(session)

    session.severity_index = round(
        min(
            1.0,
            0.55 * phq9_normalized
            + 0.25 * domain_max
            + 0.10 * domain_avg
            + crisis_boost
            + trend_boost,
        ),
        3,
    )

    if session.phq9_answers:
        session.severity_label = severity_band(phq9_total)
    elif session.severity_index >= 0.7:
        session.severity_label = "severe"
    elif session.severity_index >= 0.5:
        session.severity_label = "moderate"
    elif session.severity_index >= 0.25:
        session.severity_label = "mild"
    else:
        session.severity_label = "minimal"
