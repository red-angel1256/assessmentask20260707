# AI Mental Health Evaluation API

Multi-turn conversational backend (Python/FastAPI) implementing a strict evaluation flow with **PHQ-9 framework metrics**, **DSM-5-aligned cognitive profiling**, an **agentic state machine**, and **un-bypassable safety infrastructure**.

---

## Architecture

```
User message
    │
    ▼
┌─────────────────────────┐
│ 1. Safety Intercept     │  ← self-harm / panic loop → crisis helplines (NO LLM)
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 2. Non-Diagnostic Guard │  ← diagnosis requests → exact override phrase (NO LLM)
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 3. State Machine        │  ← PHQ-9 Q1→Q9, severity routing
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 4. Severity Index       │  ← recalculated every turn (PHQ-9 + DSM-5 domains)
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 5. LLM (optional)       │  ← only for supportive dialogue after screening
└─────────────────────────┘
```

---

## Framework Compliance

| Requirement | Implementation | Verified by |
|---|---|---|
| Multi-turn FastAPI backend | `POST /ask` with session persistence | `tests/test_evaluation.py` |
| PHQ-9 evaluation metrics | `backend/evaluation/phq9.py` — 9 questions, 0–3 scoring | `test_full_phq9_flow` |
| DSM-5 cognitive profiling | `backend/evaluation/severity.py` — mood, anxiety, cognition, behavior, self-concept | `dsm5_domains` in `/ask` response |
| Agentic state machine | `backend/state_machine.py` — programmatic flow control | `state_transition` in `/ask` response |
| Dynamic severity index | `recalculate_severity()` on every turn | `test_severity_increases_with_worse_answers` |
| Dynamic evaluation path | Mid-screening + SUPPORT regression routing in `state_machine.py` | `tests/test_routing.py` |
| Hard safety layer (pre-LLM) | `backend/safety.py` — self-harm + panic loop intercept | `tests/test_safety.py` |
| Crisis helpline injection | `build_crisis_response()` — 988, Crisis Text Line, IASP | `test_crisis_bypasses_llm` |
| Non-diagnostic boundary | `backend/guardrails.py` — exact override phrase | `test_diagnosis_exact_phrase` |
| No low-code platforms | Pure Python/FastAPI codebase | No Voiceflow/Langflow/Bubble |

---

## Key Features

| Feature | Implementation |
|---------|----------------|
| PHQ-9 evaluation | 9 structured questions, 0–3 scoring, severity bands |
| DSM-5 cognitive profiling | Mood, anxiety, cognition, behavior, self-concept domains |
| Dynamic severity index | Weighted score recalculated on every turn |
| State machine | `INTAKE → PHQ9_Q1…Q9 → ESCALATION/SUPPORT` with **on-the-fly rerouting** |
| Safety layer | Pre-LLM intercept; crisis helplines injected instantly |
| Non-diagnostic boundary | Exact phrase: `"I do not diagnose medical conditions."` |

---

## Dynamic Routing Rules

The state machine recalculates severity **before** every routing decision and can alter the evaluation path mid-conversation:

```
INTAKE → PHQ9_Q1…Q9
              │
              ├─ severity_index ≥ 0.55 ──────────► ESCALATION (early_severity_index)
              ├─ DSM-5 mood spike ≥ 0.5 ────────► ESCALATION (early_dsm5_mood_spike)
              ├─ DSM-5 self_concept spike ≥ 0.5 ► ESCALATION (early_dsm5_self_concept_spike)
              ├─ PHQ-9 Q9 score ≥ 2 ────────────► CRISIS
              │
              └─ all 9 answered ─────────────────► ESCALATION or SUPPORT
                                                    │
SUPPORT ◄───────────────────────────────────────────┘
   │
   └─ severity rises again ───────────────────────► ESCALATION (support_regression)
```

| Trigger | Threshold | Result |
|---|---|---|
| Severity index (mid-PHQ-9) | `≥ 0.55` | Skip remaining questions → `ESCALATION` |
| DSM-5 mood domain spike | `≥ 0.5` | Skip remaining questions → `ESCALATION` |
| DSM-5 self-concept spike | `≥ 0.5` | Skip remaining questions → `ESCALATION` |
| PHQ-9 complete + high band | `moderately_severe` / `severe` | `ESCALATION` |
| SUPPORT + severity rises | `≥ 0.55` | `ESCALATION` (support regression) |

`evaluation_path` in the API response reflects which rule fired (e.g. `escalation_early_dsm5_self_concept_spike`).

---

## Project Structure

```
backend/
├── main.py              # FastAPI pipeline (safety → guardrails → state machine → LLM)
├── safety.py            # Crisis intercept (self-harm, panic loop)
├── guardrails.py        # Non-diagnostic boundary
├── state_machine.py     # Agentic evaluation flow
├── session_store.py     # In-memory session state
├── ai_agent.py          # LLM formatter (post-safety only)
├── tools.py             # MedGemma, therapist search, geolocation
├── config.py            # Environment config
└── evaluation/
    ├── phq9.py          # PHQ-9 questions, parsing, scoring
    └── severity.py      # Dynamic severity index + DSM-5 domains

tests/
├── test_safety.py       # Crisis + diagnosis guard tests
├── test_evaluation.py   # PHQ-9 flow + severity routing tests
├── test_session.py      # Session metadata + GET /session tests
└── test_routing.py      # Mid-flow dynamic routing tests

frontend.py              # Streamlit UI (optional)
```

---

## API

### `POST /ask`

**Request:**
```json
{
  "message": "Hello",
  "session_id": "optional-uuid",
  "history": []
}
```

**Response:**
```json
{
  "response": "...",
  "session_id": "uuid",
  "session_state": "PHQ9_Q1",
  "severity_index": 0.12,
  "severity_label": "minimal",
  "safety_triggered": false,
  "evaluation_path": "phq9_screening",
  "phq9_total": null,
  "phq9_complete": false,
  "tool_called": "None",
  "dsm5_domains": {
    "mood": 0.0,
    "anxiety": 0.0,
    "cognition": 0.0,
    "behavior": 0.0,
    "self_concept": 0.0
  },
  "state_transition": "INTAKE → PHQ9_Q1"
}
```

### `GET /session/{session_id}`

Inspect live evaluation state without sending a message. Returns severity index, PHQ-9 progress, DSM-5 domain scores, evaluation path, and last state transition.

**Response:**
```json
{
  "session_id": "uuid",
  "session_state": "PHQ9_Q3",
  "severity_index": 0.22,
  "severity_label": "mild",
  "evaluation_path": "phq9_screening",
  "dsm5_domains": { "mood": 0.3, "anxiety": 0.0, "cognition": 0.0, "behavior": 0.0, "self_concept": 0.0 },
  "phq9_total": 3,
  "phq9_complete": false,
  "phq9_answered": 2,
  "phq9_current_question": 3,
  "turn_count": 3,
  "distress_turn_count": 0,
  "last_state_transition": "PHQ9_Q2 → PHQ9_Q3"
}
```

### Other endpoints

- `GET /health` — health check
- `POST /session/reset` — clear session state

---

## Running Locally

```bash
# Install
uv venv && source .venv/Scripts/activate   # Windows Git Bash
uv pip install -e ".[dev]"

# Environment
echo "HF_API_KEY=your_key" > .env

# Backend
uvicorn backend.main:app --reload

# Frontend (optional)
streamlit run frontend.py
```

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs

---

## Testing

```bash
pytest tests/ -v
```

Critical test coverage:
- Crisis messages bypass LLM and return helplines
- Diagnosis requests return exact non-diagnostic phrase
- Full 9-question PHQ-9 flow with scoring
- Q9 score ≥ 2 triggers crisis path
- High severity routes to escalation
- Mid-PHQ-9 severity spike skips to escalation
- DSM-5 domain spike short-circuits remaining PHQ-9 questions
- SUPPORT state regresses to ESCALATION when severity rises

### Manual smoke tests

```bash
# Crisis (instant, no LLM)
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "I want to kill myself"}'

# Diagnosis block
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Do I have depression?"}'

# Start PHQ-9 screening
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'

# Inspect session state (replace SESSION_ID)
curl http://localhost:8000/session/SESSION_ID
```

---

## Safety Guarantees

1. **Self-harm language** → pipeline terminates before LLM; crisis helplines injected
2. **Panic loop** (3+ distress messages) → same crisis path
3. **PHQ-9 Q9 score ≥ 2** → crisis path
4. **Diagnosis requests** → exact override, no LLM
5. State machine controls evaluation path — LLM does not decide screening flow

---

## Disclaimer

Educational and research purposes only. Not a replacement for professional therapy or medical advice.

MIT License
"# 2026-07-07-Founding-Engineer-Screening-Assignment-24-Hour-Challenge-" 
