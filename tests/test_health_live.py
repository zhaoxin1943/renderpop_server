from fastapi.testclient import TestClient

from app.main import app


def test_live_does_not_need_database() -> None:
    client = TestClient(app)
    response = client.get("/api/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"
