import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.session_store import session_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_sessions():
    session_store.reset()
    yield
    session_store.reset()


@patch("backend.main.generate_response")
def test_dsm5_spike_skips_remaining_phq9(mock_generate):
    """Mood/self-concept spike mid-screening → early ESCALATION, PHQ-9 incomplete."""
    session_id = "early-dsm5-test"

    client.post("/ask", json={"message": "Hi", "session_id": session_id, "history": []})
    client.post(
        "/ask",
        json={"message": "1", "session_id": session_id, "history": []},
    )
    resp = client.post(
        "/ask",
        json={
            "message": (
                "3 - I feel hopeless with no interest in anything, "
                "worthless and bad about myself"
            ),
            "session_id": session_id,
            "history": [],
        },
    )
    data = resp.json()

    assert data["session_state"] == "ESCALATION"
    assert data["evaluation_path"] in (
        "escalation_early_dsm5_mood_spike",
        "escalation_early_dsm5_self_concept_spike",
    )
    assert data["phq9_complete"] is False
    assert data["phq9_answered"] == 2
    mock_generate.assert_not_called()


@patch("backend.main.generate_response")
def test_high_severity_mid_phq9_triggers_early_escalation(mock_generate):
    """Severity index ≥ 0.55 before Q9 completes → skip to ESCALATION."""
    session_id = "early-severity-test"

    client.post("/ask", json={"message": "Hi", "session_id": session_id, "history": []})
    for _ in range(7):
        client.post(
            "/ask",
            json={"message": "3", "session_id": session_id, "history": []},
        )

    resp = client.post(
        "/ask",
        json={
            "message": "3 hopeless worthless failure guilty",
            "session_id": session_id,
            "history": [],
        },
    )
    data = resp.json()

    assert data["session_state"] == "ESCALATION"
    assert data["evaluation_path"].startswith("escalation_early_")
    assert data["severity_index"] >= 0.55
    assert data["phq9_complete"] is False
    assert data["phq9_answered"] == 8
    mock_generate.assert_not_called()


@patch("backend.main.generate_response")
def test_support_regression_to_escalation(mock_generate):
    """SUPPORT state re-routes to ESCALATION when severity rises on a later turn."""
    mock_generate.return_value = ("Supportive follow-up.", "None")
    session_id = "support-regression-test"

    client.post("/ask", json={"message": "Hi", "session_id": session_id, "history": []})
    for _ in range(9):
        client.post(
            "/ask",
            json={"message": "0", "session_id": session_id, "history": []},
        )

    support_data = client.post(
        "/ask",
        json={"message": "Just checking in", "session_id": session_id, "history": []},
    ).json()
    assert support_data["session_state"] == "SUPPORT"

    resp = client.post(
        "/ask",
        json={
            "message": (
                "I feel hopeless, sad, depressed, worthless, like a failure, "
                "guilty, bad about myself, and I can't go on"
            ),
            "session_id": session_id,
            "history": [],
        },
    )
    data = resp.json()

    assert data["session_state"] == "ESCALATION"
    assert data["evaluation_path"] == "escalation_support_regression"
    assert (
        data["dsm5_domains"]["mood"] >= 0.5
        or data["dsm5_domains"]["self_concept"] >= 0.5
    )
    assert "988" in data["response"]
