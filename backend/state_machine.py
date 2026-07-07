"""Agentic state machine — programmatic evaluation flow control."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.evaluation.phq9 import (
    calculate_total,
    format_question,
    is_complete,
    parse_phq9_answer,
    q9_triggers_crisis,
    severity_band,
)
from backend.evaluation.severity import (
    escalation_reason,
    recalculate_severity,
    should_escalate,
)
from backend.session_store import SessionState

INTAKE_MESSAGE = (
    "Welcome. I'm here to support you through a brief wellbeing check-in. "
    "This is not a diagnosis — just a structured conversation to understand how you've been feeling.\n\n"
)


@dataclass
class TurnResult:
    response: str
    needs_llm: bool = False
    llm_context: str = ""
    tool_hint: Optional[str] = None


def _state_name_for_question(q: int) -> str:
    return f"PHQ9_Q{q}"


def _begin_phq9(session: SessionState) -> TurnResult:
    session.phq9_current_question = 1
    session.current_state = _state_name_for_question(1)
    session.evaluation_path = "phq9_screening"
    return TurnResult(response=INTAKE_MESSAGE + format_question(1))


def _escalation_message(
    total: int,
    band: str,
    severity_index: float,
    *,
    answered: int = 9,
    reason: str = "severity_index",
) -> str:
    progress_line = (
        f"PHQ-9 score so far: {total}/27 ({band.replace('_', ' ')}) — "
        f"{answered} of 9 questions answered\n"
        if answered < 9
        else f"PHQ-9 score: {total}/27 ({band.replace('_', ' ')})\n"
    )
    routing_note = {
        "severity_index": "Your cumulative severity index crossed the escalation threshold mid-screening.",
        "dsm5_mood_spike": "Elevated mood-domain signals were detected during screening.",
        "dsm5_self_concept_spike": "Elevated self-concept distress signals were detected during screening.",
        "support_regression": "Your latest message raised the severity index above the escalation threshold.",
    }.get(reason, "Your responses indicate heightened distress.")

    return (
        f"Thank you for sharing honestly — that takes courage.\n\n"
        f"{progress_line}"
        f"Severity index: {severity_index}\n"
        f"{routing_note}\n\n"
        "Your responses suggest you may benefit from professional support. "
        "I recommend reaching out to a licensed mental health professional.\n\n"
        "Resources:\n"
        "• 988 Suicide & Crisis Lifeline (US): Call or text 988\n"
        "• SAMHSA Helpline: 1-800-662-4357\n"
        "• Find A Helpline: https://findahelpline.com\n\n"
        "Would you like help finding therapists near you? Share your city or say 'near me'."
    )


def _support_message(total: int, band: str, severity_index: float) -> str:
    return (
        f"Thank you for completing the check-in.\n\n"
        f"PHQ-9 score: {total}/27 ({band.replace('_', ' ')})\n"
        f"Severity index: {severity_index}\n\n"
        "Based on your responses, continuing supportive conversation may help. "
        "What's been weighing on you most lately?"
    )


def _route_to_escalation(
    session: SessionState,
    *,
    path_suffix: str,
    reason: str,
) -> TurnResult:
    total = calculate_total(session.phq9_answers)
    answered = len(session.phq9_answers)
    band = severity_band(total) if answered >= 9 else "incomplete"

    session.current_state = "ESCALATION"
    session.evaluation_path = f"escalation_{path_suffix}"
    return TurnResult(
        response=_escalation_message(
            total,
            band,
            session.severity_index,
            answered=answered,
            reason=reason,
        ),
        tool_hint="locate_therapists",
    )


def _process_phq9_answer(session: SessionState, message: str) -> TurnResult:
    q = session.phq9_current_question
    score = parse_phq9_answer(message)

    if score is None:
        recalculate_severity(session, message)
        return TurnResult(
            response=(
                "I didn't catch a clear answer. Please choose one:\n"
                "  • Not at all (0)\n"
                "  • Several days (1)\n"
                "  • More than half the days (2)\n"
                "  • Nearly every day (3)"
            )
        )

    session.phq9_answers[q] = score
    recalculate_severity(session, message)

    if q == 9 and q9_triggers_crisis(session.phq9_answers):
        session.current_state = "CRISIS"
        session.evaluation_path = "crisis_phq9_q9"
        return TurnResult(response="__CRISIS_Q9__")

    if should_escalate(session):
        return _route_to_escalation(
            session,
            path_suffix=f"early_{escalation_reason(session)}",
            reason=escalation_reason(session),
        )

    if q < 9:
        next_q = q + 1
        session.phq9_current_question = next_q
        session.current_state = _state_name_for_question(next_q)
        return TurnResult(response=format_question(next_q))

    return _route_after_phq9(session)


def _route_after_phq9(session: SessionState) -> TurnResult:
    total = calculate_total(session.phq9_answers)
    band = severity_band(total)
    session.current_state = "SEVERITY_ROUTING"

    if should_escalate(session) or band in ("moderately_severe", "severe"):
        return _route_to_escalation(
            session,
            path_suffix="high_severity",
            reason=escalation_reason(session),
        )

    session.current_state = "SUPPORT"
    session.evaluation_path = "supportive_dialogue"
    return TurnResult(
        response=_support_message(total, band, session.severity_index),
        needs_llm=True,
        llm_context=(
            f"User completed PHQ-9 with score {total}/27 ({band}). "
            f"Severity index: {session.severity_index}. "
            "Provide warm, supportive follow-up. Do not diagnose."
        ),
    )


def process_turn(session: SessionState, message: str) -> TurnResult:
    """Advance state machine based on current state and user message."""
    session.turn_count += 1
    state = session.current_state

    if state == "INTAKE":
        recalculate_severity(session, message)
        result = _begin_phq9(session)
    elif state.startswith("PHQ9_Q"):
        result = _process_phq9_answer(session, message)
    elif state == "SUPPORT":
        recalculate_severity(session, message)
        if should_escalate(session):
            result = _route_to_escalation(
                session,
                path_suffix="support_regression",
                reason="support_regression",
            )
        else:
            session.evaluation_path = "supportive_dialogue"
            result = TurnResult(
                response="",
                needs_llm=True,
                llm_context=message,
            )
    elif state == "ESCALATION":
        recalculate_severity(session, message)
        if any(kw in message.lower() for kw in ("therapist", "near me", "find", "help")):
            result = TurnResult(
                response="",
                needs_llm=True,
                llm_context=message,
                tool_hint="locate_therapists",
            )
        else:
            result = TurnResult(
                response=(
                    "I'm here for you. If you'd like therapist recommendations, "
                    "tell me your city or say 'near me'."
                )
            )
    elif state == "COMPLETE":
        recalculate_severity(session, message)
        result = TurnResult(
            response="This check-in is complete. I'm still here if you'd like to talk.",
            needs_llm=True,
            llm_context=message,
        )
    elif state in ("NON_DIAGNOSTIC", "CRISIS"):
        session.current_state = "INTAKE"
        recalculate_severity(session, message)
        result = _begin_phq9(session)
    else:
        recalculate_severity(session, message)
        result = TurnResult(response="How can I support you right now?")

    return result


def get_phq9_progress(session: SessionState) -> dict:
    total = calculate_total(session.phq9_answers) if session.phq9_answers else None
    return {
        "phq9_total": total,
        "phq9_complete": is_complete(session.phq9_answers),
        "phq9_answered": len(session.phq9_answers),
    }
