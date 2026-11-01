from fastapi.testclient import TestClient

from app.main import create_app


def test_health():
    response = TestClient(create_app(init_database=False)).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
