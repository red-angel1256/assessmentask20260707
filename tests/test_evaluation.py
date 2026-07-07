import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.session_store import session_store

client = TestClient(app)

PHQ9_ANSWERS = ["0", "1", "2", "1", "0", "1", "2", "1", "0"]


@pytest.fixture(autouse=True)
def clear_sessions():
    session_store.reset()
    yield
    session_store.reset()


@patch("backend.main.generate_response")
def test_full_phq9_flow(mock_generate):
    mock_generate.return_value = ("Supportive follow-up.", "None")
    session_id = "phq9-flow-test"

    resp = client.post(
        "/ask",
        json={"message": "Hello", "session_id": session_id, "history": []},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_state"] == "PHQ9_Q1"
    assert "Question 1 of 9" in data["response"]

    for i, answer in enumerate(PHQ9_ANSWERS):
        resp = client.post(
            "/ask",
            json={"message": answer, "session_id": session_id, "history": []},
        )
        data = resp.json()

        if i < 8:
            assert data["session_state"] == f"PHQ9_Q{i + 2}"
        assert data["severity_index"] >= 0

    assert data["phq9_complete"] is True
    assert data["phq9_total"] == sum(int(a) for a in PHQ9_ANSWERS)
    assert data["session_state"] in ("SUPPORT", "ESCALATION")


@patch("backend.main.generate_response")
def test_q9_high_score_triggers_crisis(mock_generate):
    session_id = "q9-crisis-test"
    answers = ["0"] * 8 + ["2"]

    client.post("/ask", json={"message": "Hi", "session_id": session_id, "history": []})
    for answer in answers:
        resp = client.post(
            "/ask",
            json={"message": answer, "session_id": session_id, "history": []},
        )

    data = resp.json()
    assert data["safety_triggered"] is True
    assert data["session_state"] == "CRISIS"
    assert "988" in data["response"]
    mock_generate.assert_not_called()


@patch("backend.main.generate_response")
def test_severity_increases_with_worse_answers(mock_generate):
    mock_generate.return_value = ("ok", "None")
    session_id = "severity-test"

    client.post("/ask", json={"message": "Hi", "session_id": session_id, "history": []})

    low_resp = client.post(
        "/ask",
        json={"message": "0", "session_id": session_id, "history": []},
    )
    low_index = low_resp.json()["severity_index"]

    session_id = "severity-test-2"
    client.post("/ask", json={"message": "Hi", "session_id": session_id, "history": []})
    high_resp = client.post(
        "/ask",
        json={"message": "3", "session_id": session_id, "history": []},
    )
    high_index = high_resp.json()["severity_index"]

    assert high_index > low_index


@patch("backend.main.generate_response")
def test_high_severity_routes_to_escalation(mock_generate):
    session_id = "escalation-test"
    high_answers = ["3"] * 8 + ["0"]  # high severity but Q9 below crisis threshold

    client.post("/ask", json={"message": "Hi", "session_id": session_id, "history": []})
    for answer in high_answers:
        resp = client.post(
            "/ask",
            json={"message": answer, "session_id": session_id, "history": []},
        )

    data = resp.json()
    assert data["session_state"] == "ESCALATION"
    assert data["evaluation_path"] == "escalation_high_severity"
    assert data["phq9_total"] == 24
