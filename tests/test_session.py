import pytest

from fastapi.testclient import TestClient



from backend.main import app

from backend.session_store import session_store



client = TestClient(app)



DSM5_DOMAIN_NAMES = {"mood", "anxiety", "cognition", "behavior", "self_concept"}





@pytest.fixture(autouse=True)

def clear_sessions():

    session_store.reset()

    yield

    session_store.reset()





def test_ask_includes_dsm5_domains_and_state_transition():

    resp = client.post(

        "/ask",

        json={"message": "Hello", "session_id": "meta-test", "history": []},

    )

    data = resp.json()



    assert resp.status_code == 200

    assert set(data["dsm5_domains"].keys()) == DSM5_DOMAIN_NAMES

    assert all(isinstance(v, (int, float)) for v in data["dsm5_domains"].values())

    assert data["state_transition"] == "INTAKE → PHQ9_Q1"





def test_dsm5_domains_update_from_free_text():

    session_id = "dsm5-update-test"

    client.post("/ask", json={"message": "Hi", "session_id": session_id, "history": []})

    resp = client.post(

        "/ask",

        json={

            "message": "I've been feeling hopeless and anxious lately",

            "session_id": session_id,

            "history": [],

        },

    )

    data = resp.json()



    assert data["dsm5_domains"]["mood"] > 0

    assert data["dsm5_domains"]["anxiety"] > 0





def test_get_session_returns_snapshot():

    session_id = "snapshot-test"

    client.post("/ask", json={"message": "Hello", "session_id": session_id, "history": []})



    resp = client.get(f"/session/{session_id}")

    data = resp.json()



    assert resp.status_code == 200

    assert data["session_id"] == session_id

    assert data["session_state"] == "PHQ9_Q1"

    assert data["last_state_transition"] == "INTAKE → PHQ9_Q1"

    assert set(data["dsm5_domains"].keys()) == DSM5_DOMAIN_NAMES

    assert data["phq9_current_question"] == 1





def test_get_session_not_found():

    resp = client.get("/session/nonexistent-session-id")

    assert resp.status_code == 404


