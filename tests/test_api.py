import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import MemorySaver

from app import api
from app.graph import build_graph
from main import app


@pytest.fixture
def client(env, monkeypatch):
    monkeypatch.setattr(api, "graph", build_graph(MemorySaver()))
    return TestClient(app)


def _create(client):
    r = client.post("/api/webhooks/github",
                    json={"repository_url": "https://github.com/o/r", "branch": "feature/messy"})
    assert r.status_code == 200
    return r.json()["thread_id"]


def test_webhook_starts_thread_and_pauses(client):
    tid = _create(client)
    data = client.get(f"/api/reviews/{tid}").json()
    assert data["next"] == ["apply_changes_node"]
    assert data["state"]["pr_url"] == "https://github.com/o/r/tree/feature/messy"
    assert "a.py" in data["state"]["lint_errors"]


def test_webhook_validation_error(client):
    assert client.post("/api/webhooks/github", json={"foo": "bar"}).status_code == 422


def test_unknown_thread_404(client):
    r = client.post("/api/reviews/nope/approve", json={"approved": True})
    assert r.status_code == 404


def test_reject_without_feedback_422(client):
    tid = _create(client)
    assert client.post(f"/api/reviews/{tid}/approve", json={"approved": False}).status_code == 422


def test_bad_body_422(client):
    tid = _create(client)
    assert client.post(f"/api/reviews/{tid}/approve", json={"approved": "maybe?"}).status_code == 422


def test_full_flow_reject_then_approve_then_409(client, env):
    tid = _create(client)
    r = client.post(f"/api/reviews/{tid}/approve",
                    json={"approved": False, "feedback": "Use list comprehensions instead of loops"})
    assert r.status_code == 200
    assert len(env["prompts"]) == 2
    assert "list comprehensions" in env["prompts"][-1]
    assert client.get(f"/api/reviews/{tid}").json()["next"] == ["apply_changes_node"]

    assert client.post(f"/api/reviews/{tid}/approve", json={"approved": True}).status_code == 200
    assert env["commits"] == ["a.py"]
    assert client.get(f"/api/reviews/{tid}").json()["next"] == []

    # finished thread can't be approved again
    assert client.post(f"/api/reviews/{tid}/approve", json={"approved": True}).status_code == 409
