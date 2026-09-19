import pytest
from fastapi.testclient import TestClient
from src.presentation.api.app import create_app

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_get_agents_config(client):
    response = client.get("/config/agents")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 7  # 6 default + learning
    # Check that learning is present
    roles = [a["id"] for a in data]
    assert "learning" in roles
    
    # By default, should have provider and model_name
    assert "provider" in data[0]
    assert "model_name" in data[0]

def test_put_agent_config(client):
    # Test updating the judge
    payload = {
        "provider": "openai",
        "model_name": "gpt-4o"
    }
    response = client.put("/config/agents/the_judge", json=payload)
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    
    # Verify the update is reflected in GET
    response_get = client.get("/config/agents")
    judge_config = next(c for c in response_get.json() if c["id"] == "the_judge")
    assert judge_config["provider"] == "openai"
    assert judge_config["model_name"] == "gpt-4o"

def test_put_agent_config_invalid_role(client):
    payload = {
        "provider": "openai",
        "model_name": "gpt-4o"
    }
    response = client.put("/config/agents/invalid_role", json=payload)
    assert response.status_code == 404
