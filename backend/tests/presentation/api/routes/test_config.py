import pytest
from fastapi.testclient import TestClient
from src.presentation.api.app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_get_agents_config(client: TestClient):
    response = client.get("/config/agents")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 6
    assert data[0]["id"] == "nl_interpreter"
    assert data[0]["name"] == "Nl Interpreter"
