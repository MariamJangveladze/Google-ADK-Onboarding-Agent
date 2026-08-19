from fastapi.testclient import TestClient

from onboarding_agent.api import app


def test_complete_demo_journey(monkeypatch):
    monkeypatch.setenv("ONBOARDING_RUNTIME_MODE", "local")
    with TestClient(app) as client:
        welcome = client.post(
            "/demo/start",
            json={"slack_user_id": "U_DEMO", "verified_email": "nino@example.com"},
        )
        task = client.post(
            "/demo/chat",
            json={"slack_user_id": "U_DEMO", "message": "ready"},
        )
        policy = client.post(
            "/demo/chat",
            json={"slack_user_id": "U_DEMO", "message": "What is the security policy?"},
        )
        done = client.post("/demo/done", json={"slack_user_id": "U_DEMO"})

    assert welcome.status_code == 200
    assert welcome.json()["action"] == "WELCOME"
    assert welcome.json()["citations"]
    assert task.json()["action"] == "TASK_ASSIGNED"
    assert task.json()["task"]["id"] == "TASK-001"
    assert policy.json()["action"] == "ANSWER"
    assert policy.json()["citations"]
    assert done.json()["action"] == "TASK_COMPLETED"
    assert done.json()["task"]["id"] == "TASK-002"


def test_unverified_identity_cannot_access_tasks(monkeypatch):
    monkeypatch.setenv("ONBOARDING_RUNTIME_MODE", "local")
    with TestClient(app) as client:
        response = client.post(
            "/demo/start",
            json={"slack_user_id": "U_ATTACKER", "verified_email": "unknown@example.com"},
        )
    assert response.status_code == 200
    assert response.json()["action"] == "IDENTITY_REQUIRED"
