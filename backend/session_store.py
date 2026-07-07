"""In-memory session store for multi-turn evaluation state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class SessionState:
    session_id: str
    current_state: str = "INTAKE"
    phq9_answers: Dict[int, int] = field(default_factory=dict)
    phq9_current_question: int = 0
    dsm5_domains: Dict[str, float] = field(default_factory=dict)
    severity_index: float = 0.0
    severity_label: str = "minimal"
    distress_turn_count: int = 0
    evaluation_path: str = "intake"
    turn_count: int = 0
    last_state_transition: str = "INTAKE"


class SessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionState] = {}

    def get_or_create(self, session_id: Optional[str]) -> SessionState:
        sid = session_id or str(uuid.uuid4())
        if sid not in self._sessions:
            self._sessions[sid] = SessionState(session_id=sid)
        return self._sessions[sid]

    def get(self, session_id: str) -> Optional[SessionState]:
        return self._sessions.get(session_id)

    def save(self, session: SessionState) -> None:
        self._sessions[session.session_id] = session

    def reset(self) -> None:
        self._sessions.clear()


session_store = SessionStore()
