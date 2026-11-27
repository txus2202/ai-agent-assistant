import pytest
from fastapi.testclient import TestClient
from src.presentation.api.app import create_app

from src.domain.entities.user import User
from src.presentation.api.dependencies.auth import get_current_user

@pytest.fixture
def test_user():
    return User(
        id="test-user-id",
        username="testadmin",
        password_hash="fakehash",
        is_admin=True,
        is_active=True,
    )

@pytest.fixture
def client(test_user):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    return TestClient(app)

def test_get_agents_config_unauthenticated():
    raw_app = create_app()
    raw_client = TestClient(raw_app)
    response = raw_client.get("/config/agents")
    assert response.status_code == 401

def test_per_user_agent_config_isolation(test_user):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    client1 = TestClient(app)

    # User 1 sets the_judge to openai / gpt-4o
    res1 = client1.put("/config/agents/the_judge", json={"provider": "openai", "model_name": "gpt-4o"})
    assert res1.status_code == 200

    # Switch to User 2
    user2 = User(id="user-2-id", username="operator2", password_hash="hash2", is_admin=False)
    app.dependency_overrides[get_current_user] = lambda: user2
    client2 = TestClient(app)

    # User 2 sets the_judge to anthropic / claude-3-5-sonnet
    res2 = client2.put("/config/agents/the_judge", json={"provider": "anthropic", "model_name": "claude-3-5-sonnet"})
    assert res2.status_code == 200

    # Verify User 2 gets claude-3-5-sonnet
    assert client2.get("/config/agents/the_judge").json()["model_name"] == "claude-3-5-sonnet"

    # Switch back to User 1 and verify gpt-4o is preserved
    app.dependency_overrides[get_current_user] = lambda: test_user
    assert client1.get("/config/agents/the_judge").json()["model_name"] == "gpt-4o"

def test_get_agents_config(client):
    response = client.get("/config/agents")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 7  # 6 default + learning
    # Check that learning is present
    roles = [a["id"] for a in data]
    assert "learning" in roles
    assert "supervisor" in roles
    supervisor_agent = next(a for a in data if a["id"] == "supervisor")
    assert supervisor_agent["color_hex"] == "#f59e0b"
    assert supervisor_agent["name"] == "Atenea"
    
    # By default, should have provider, model_name, name, description, and color_hex
    assert "provider" in data[0]
    assert "model_name" in data[0]
    assert "name" in data[0]
    assert "description" in data[0]
    assert len(data[0]["description"]) > 10
    assert "color_hex" in data[0]
    assert data[0]["color_hex"].startswith("#")

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
    assert judge_config["rag_top_k"] == 5
    assert judge_config["rag_min_score"] == pytest.approx(0.3)


def test_put_agent_config_with_rag_params_and_preservation(client):
    # 1. Update provider, model, and custom RAG settings
    payload = {
        "provider": "gemini",
        "model_name": "gemini-2.5-flash",
        "rag_top_k": 12,
        "rag_min_score": 0.55,
    }
    res = client.put("/config/agents/senior_architect", json=payload)
    assert res.status_code == 200

    cfg = client.get("/config/agents/senior_architect").json()
    assert cfg["rag_top_k"] == 12
    assert cfg["rag_min_score"] == pytest.approx(0.55)

    # 2. Subsequent model-only update preserves rag_top_k and rag_min_score
    res2 = client.put(
        "/config/agents/senior_architect",
        json={"provider": "openai", "model_name": "gpt-4o"},
    )
    assert res2.status_code == 200
    cfg2 = client.get("/config/agents/senior_architect").json()
    assert cfg2["provider"] == "openai"
    assert cfg2["model_name"] == "gpt-4o"
    assert cfg2["rag_top_k"] == 12
    assert cfg2["rag_min_score"] == pytest.approx(0.55)


@pytest.mark.parametrize(
    "invalid_payload",
    [
        {"provider": "gemini", "model_name": "gemini-2.5-flash", "rag_top_k": -1},
        {"provider": "gemini", "model_name": "gemini-2.5-flash", "rag_top_k": 51},
        {"provider": "gemini", "model_name": "gemini-2.5-flash", "rag_min_score": -0.05},
        {"provider": "gemini", "model_name": "gemini-2.5-flash", "rag_min_score": 1.05},
    ],
)
def test_put_agent_config_validates_rag_bounds(client, invalid_payload):
    response = client.put("/config/agents/senior_architect", json=invalid_payload)
    assert response.status_code == 422

def test_agent_config_defaults_from_profile_or_empty(test_user):
    from src.domain.agents.sub_agent_profiles import SubAgentProfile

    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    local_client = TestClient(app)

    # Agent with defaults in profile
    custom_profile = SubAgentProfile(
        id="test_custom_agent",
        display_name="Custom Agent",
        description="Agent with explicit default model in profile.",
        color_hex="#123456",
        system_prompt="Test prompt",
        default_provider="gemini",
        default_model="gemini-3.8-flash",
    )
    # Agent without defaults in profile
    empty_profile = SubAgentProfile(
        id="test_empty_agent",
        display_name="Empty Agent",
        description="Agent with no default model in profile.",
        color_hex="#654321",
        system_prompt="Test prompt",
    )
    app.state.agent_catalog.register_profile(custom_profile)
    app.state.agent_catalog.register_profile(empty_profile)

    try:
        cfg_custom = local_client.get("/config/agents/test_custom_agent").json()
        assert cfg_custom["provider"] == "gemini"
        assert cfg_custom["model_name"] == "gemini-3.8-flash"

        cfg_empty = local_client.get("/config/agents/test_empty_agent").json()
        assert cfg_empty["provider"] == ""
        assert cfg_empty["model_name"] == ""
    finally:
        app.state.agent_catalog.unregister_profile("test_custom_agent")
        app.state.agent_catalog.unregister_profile("test_empty_agent")


def test_put_agent_config_invalid_role(client):
    payload = {
        "provider": "openai",
        "model_name": "gpt-4o"
    }
    response = client.put("/config/agents/invalid_role", json=payload)
    assert response.status_code == 404

def test_get_topology(client):
    from src.infrastructure.config.yaml_topology_provider import load_topology
    top = load_topology()
    response = client.get("/config/topology")
    assert response.status_code == 200
    data = response.json()
    assert data["project_name"] == top.project_name
    assert "Asistente Técnica y Evaluadora" in data["project_description"]
    assert "supervisor" in data
    assert data["supervisor"] == "Atenea"
    assert "interpreters" in data
    assert "proposers" in data
    assert "reviewers" in data
    assert "evaluators" in data
    assert "implementers" in data
    assert isinstance(data["interpreters"], list)

def test_get_topology_unauthenticated():
    raw_app = create_app()
    raw_client = TestClient(raw_app)
    response = raw_client.get("/config/topology")
    assert response.status_code == 200
    data = response.json()
    assert "project_name" in data
    assert data["is_customized"] is False
    assert isinstance(data["review_rounds"], int)


def test_put_and_delete_topology_require_authentication():
    raw_app = create_app()
    raw_client = TestClient(raw_app)
    assert raw_client.put("/config/topology", json={"proposers": ["Hestia"], "review_rounds": 1}).status_code == 401
    assert raw_client.delete("/config/topology").status_code == 401


def test_per_user_topology_crud_isolation_and_reset(tmp_path):
    from src.presentation.api.config import Settings

    settings = Settings(
        sqlite_db_path=tmp_path / "topology_api.db",
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
        review_rounds=2,
    )
    app = create_app(settings=settings)
    user1 = User(id="topo-u1", username="alice", password_hash="h", is_admin=False, is_active=True)
    user2 = User(id="topo-u2", username="bob", password_hash="h", is_admin=False, is_active=True)

    app.dependency_overrides[get_current_user] = lambda: user1
    client = TestClient(app)

    # 1. First-time access shows canonical topology.yaml + REVIEW_ROUNDS (2)
    initial = client.get("/config/topology").json()
    assert initial["is_customized"] is False
    assert initial["review_rounds"] == 2
    assert initial["supervisor"] == "Atenea"
    assert len(initial["eligible_agents"]) >= 5
    eligible_ids = {a["id"] for a in initial["eligible_agents"]}
    assert "supervisor" not in eligible_ids
    assert "learning" not in eligible_ids

    # 2. User 1 moves Hefesto into proposers and sets review_rounds = 4
    put_res = client.put(
        "/config/topology",
        json={
            "interpreters": [],
            "proposers": ["Hestia", "devops_secops"],
            "reviewers": ["Sphinx"],
            "evaluators": ["Sphinx"],
            "implementers": ["Aracne"],
            "review_rounds": 4,
        },
    )
    assert put_res.status_code == 200
    updated = put_res.json()
    assert updated["is_customized"] is True
    assert updated["review_rounds"] == 4
    assert updated["supervisor"] == "Atenea"
    assert updated["interpreters"] == []
    assert updated["proposers"] == ["Hestia", "Hefesto"]
    assert updated["implementers"] == ["Aracne"]

    # Verify /config/agents reflects User 1's new topology_roles for Hefesto
    agents_u1 = client.get("/config/agents").json()
    hefesto_u1 = next(a for a in agents_u1 if a["id"] == "devops_secops")
    assert "proposer" in hefesto_u1["topology_roles"]
    assert "implementer" not in hefesto_u1["topology_roles"]

    # 3. Switch to User 2: completely isolated, still sees defaults
    app.dependency_overrides[get_current_user] = lambda: user2
    u2_top = client.get("/config/topology").json()
    assert u2_top["is_customized"] is False
    assert u2_top["review_rounds"] == 2
    assert "Hefesto" not in u2_top["proposers"]

    # 4. User 1 resets to defaults -> returns to topology.yaml + REVIEW_ROUNDS
    app.dependency_overrides[get_current_user] = lambda: user1
    del_res = client.delete("/config/topology")
    assert del_res.status_code == 200
    restored = del_res.json()
    assert restored["is_customized"] is False
    assert restored["review_rounds"] == 2
    assert restored["proposers"] == initial["proposers"]


def test_put_topology_rejects_supervisor_modification_or_empty_phases(tmp_path):
    from src.presentation.api.config import Settings

    settings = Settings(
        sqlite_db_path=tmp_path / "topology_invalid.db",
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
    )
    app = create_app(settings=settings)
    user1 = User(id="topo-u1", username="alice", password_hash="h", is_admin=False, is_active=True)
    app.dependency_overrides[get_current_user] = lambda: user1
    client = TestClient(app)

    # Attempt to customize supervisor
    res_sup = client.put(
        "/config/topology",
        json={
            "supervisor": "Hestia",
            "proposers": ["Hestia"],
            "review_rounds": 1,
        },
    )
    assert res_sup.status_code == 422

    # Attempt to save all execution phases empty
    res_empty = client.put(
        "/config/topology",
        json={
            "interpreters": [],
            "proposers": [],
            "reviewers": ["Sphinx"],
            "evaluators": [],
            "implementers": [],
            "review_rounds": 1,
        },
    )
    assert res_empty.status_code == 422


