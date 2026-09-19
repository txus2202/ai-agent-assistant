import pytest
import sqlite3
from src.domain.value_objects.agent_config import AgentConfig
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository

@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_config.db"
    return SqliteAgentConfigRepository(str(db_path))

def test_save_and_find(repo):
    config = AgentConfig(role="nl_interpreter", provider="gemini", model_name="gemini-3.6-flash")
    repo.save(config)
    
    found = repo.find_by_role("nl_interpreter")
    assert found is not None
    assert found.provider == "gemini"
    assert found.model_name == "gemini-3.6-flash"

def test_upsert(repo):
    config1 = AgentConfig(role="the_judge", provider="openai", model_name="gpt-4o")
    repo.save(config1)
    
    config2 = AgentConfig(role="the_judge", provider="anthropic", model_name="claude-3-opus")
    repo.save(config2)
    
    found = repo.find_by_role("the_judge")
    assert found.provider == "anthropic"
    assert found.model_name == "claude-3-opus"

def test_find_all(repo):
    repo.save(AgentConfig(role="a", provider="p1", model_name="m1"))
    repo.save(AgentConfig(role="b", provider="p2", model_name="m2"))
    
    all_configs = repo.find_all()
    assert len(all_configs) == 2
    roles = {c.role for c in all_configs}
    assert "a" in roles
    assert "b" in roles
