from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, List, Optional
import uvicorn

from backend.safety import check_safety, build_crisis_response
from backend.guardrails import is_diagnosis_request, NON_DIAGNOSTIC_PHRASE
from backend.session_store import session_store, SessionState
from backend.state_machine import process_turn, get_phq9_progress
from backend.evaluation.severity import get_dsm5_snapshot
from backend.ai_agent import generate_response

app = FastAPI(
    title="AI Mental Health Evaluation API",
    description=(
        "Multi-turn conversational backend with PHQ-9 evaluation, "
        "DSM-5 cognitive profiling, agentic state machine routing, "
        "and un-bypassable safety intercept."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class Query(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    history: Optional[List[ChatMessage]] = []
    session_id: Optional[str] = None


class AskResponse(BaseModel):
    response: str
    session_id: str
    session_state: str
    severity_index: float
    severity_label: str
    safety_triggered: bool
    evaluation_path: str
    phq9_total: Optional[int] = None
    phq9_complete: bool = False
    phq9_answered: int = 0
    tool_called: str = "None"
    dsm5_domains: Dict[str, float] = {}
    state_transition: str = ""


class SessionSnapshot(BaseModel):
    session_id: str
    session_state: str
    severity_index: float
    severity_label: str
    evaluation_path: str
    dsm5_domains: Dict[str, float]
    phq9_total: Optional[int] = None
    phq9_complete: bool = False
    phq9_answered: int = 0
    phq9_current_question: int = 0
    turn_count: int = 0
    distress_turn_count: int = 0
    last_state_transition: str = ""


def _record_transition(session: SessionState, previous_state: str) -> None:
    if previous_state != session.current_state:
        session.last_state_transition = f"{previous_state} → {session.current_state}"
    else:
        session.last_state_transition = session.current_state


def _session_snapshot(session: SessionState) -> dict:
    progress = get_phq9_progress(session)
    return {
        "session_id": session.session_id,
        "session_state": session.current_state,
        "severity_index": session.severity_index,
        "severity_label": session.severity_label,
        "evaluation_path": session.evaluation_path,
        "dsm5_domains": get_dsm5_snapshot(session),
        "phq9_total": progress["phq9_total"],
        "phq9_complete": progress["phq9_complete"],
        "phq9_answered": progress["phq9_answered"],
        "phq9_current_question": session.phq9_current_question,
        "turn_count": session.turn_count,
        "distress_turn_count": session.distress_turn_count,
        "last_state_transition": session.last_state_transition,
    }


def _build_response(
    session: SessionState,
    response_text: str,
    safety_triggered: bool = False,
    tool_called: str = "None",
) -> dict:
    snapshot = _session_snapshot(session)
    return {
        "response": response_text,
        "tool_called": tool_called,
        "safety_triggered": safety_triggered,
        "state_transition": session.last_state_transition,
        **{k: v for k, v in snapshot.items() if k != "last_state_transition"},
    }


@app.post("/ask", response_model=AskResponse)
def ask(query: Query):
    session = session_store.get_or_create(query.session_id)
    previous_state = session.current_state

    # Layer 1: Hard safety intercept — bypasses LLM entirely
    safety_result = check_safety(query.message, session)
    if safety_result.triggered:
        _record_transition(session, previous_state)
        session_store.save(session)
        return _build_response(
            session,
            build_crisis_response(safety_result.reason),
            safety_triggered=True,
        )

    # Layer 2: Non-diagnostic boundary — exact override phrase, no LLM
    if is_diagnosis_request(query.message):
        session.current_state = "NON_DIAGNOSTIC"
        session.evaluation_path = "non_diagnostic_block"
        _record_transition(session, previous_state)
        session_store.save(session)
        return _build_response(session, NON_DIAGNOSTIC_PHRASE)

    # Layer 3: Agentic state machine + dynamic severity index
    turn = process_turn(session, query.message)

    if turn.response == "__CRISIS_Q9__":
        session.current_state = "CRISIS"
        _record_transition(session, previous_state)
        session_store.save(session)
        return _build_response(
            session,
            build_crisis_response("self_harm"),
            safety_triggered=True,
        )

    tool_called = "None"
    response_text = turn.response

    # Layer 4: LLM only when state machine explicitly allows
    if turn.needs_llm:
        history = [{"role": m.role, "content": m.content} for m in (query.history or [])]
        response_text, tool_called = generate_response(
            user_message=query.message,
            history=history,
            context=turn.llm_context,
        )

    _record_transition(session, previous_state)
    session_store.save(session)
    return _build_response(session, response_text, tool_called=tool_called)


@app.get("/session/{session_id}", response_model=SessionSnapshot)
def get_session(session_id: str):
    session = session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_snapshot(session)


@app.post("/session/reset")
def reset_session(session_id: Optional[str] = None):
    if session_id and session_id in session_store._sessions:
        del session_store._sessions[session_id]
        return {"status": "session cleared", "session_id": session_id}
    session_store.reset()
    return {"status": "all sessions cleared"}


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
