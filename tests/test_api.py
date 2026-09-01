from fastapi.testclient import TestClient

from onboarding_agent.api import app
from onboarding_agent.config import get_settings

AUTH = {"Authorization": "Bearer test-token"}


def test_complete_demo_journey(monkeypatch):
    monkeypatch.setenv("ONBOARDING_RUNTIME_MODE", "local")
    monkeypatch.setenv("ONBOARDING_DEMO_API_TOKEN", "test-token")
    get_settings.cache_clear()
    with TestClient(app) as client:
        welcome = client.post(
            "/demo/start",
            json={"slack_user_id": "U_DEMO", "verified_email": "nino@example.com"},
            headers=AUTH,
        )
        task = client.post(
            "/demo/chat",
            json={"slack_user_id": "U_DEMO", "message": "ready"},
            headers=AUTH,
        )
        policy = client.post(
            "/demo/chat",
            json={"slack_user_id": "U_DEMO", "message": "What is the security policy?"},
            headers=AUTH,
        )
        done = client.post("/demo/done", json={"slack_user_id": "U_DEMO"}, headers=AUTH)

    assert welcome.status_code == 200
    assert welcome.json()["action"] == "WELCOME"
    assert welcome.json()["citations"]
    assert task.json()["action"] == "TASK_ASSIGNED"
    assert task.json()["task"]["id"] == "TASK-001"
    assert policy.json()["action"] == "ANSWER"
    assert policy.json()["citations"]
    assert done.json()["action"] == "TASK_COMPLETED"
    assert done.json()["task"]["id"] == "TASK-002"


def test_sla_endpoint_uses_the_local_container_clock(monkeypatch):
    monkeypatch.setenv("ONBOARDING_RUNTIME_MODE", "local")
    monkeypatch.setenv("ONBOARDING_DEMO_API_TOKEN", "test-token")
    get_settings.cache_clear()
    with TestClient(app) as client:
        client.post(
            "/demo/start",
            json={"slack_user_id": "U_DEMO", "verified_email": "nino@example.com"},
            headers=AUTH,
        )
        client.post(
            "/demo/chat",
            json={"slack_user_id": "U_DEMO", "message": "ready"},
            headers=AUTH,
        )
        response = client.post("/operations/sla-sweep", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == {"reminders": 0, "escalations": 0, "quiet_hours_skips": 0}


def test_unverified_identity_cannot_access_tasks(monkeypatch):
    monkeypatch.setenv("ONBOARDING_RUNTIME_MODE", "local")
    monkeypatch.setenv("ONBOARDING_DEMO_API_TOKEN", "test-token")
    get_settings.cache_clear()
    with TestClient(app) as client:
        response = client.post(
            "/demo/start",
            json={"slack_user_id": "U_ATTACKER", "verified_email": "unknown@example.com"},
            headers=AUTH,
        )
    assert response.status_code == 200
    assert response.json()["action"] == "IDENTITY_REQUIRED"
