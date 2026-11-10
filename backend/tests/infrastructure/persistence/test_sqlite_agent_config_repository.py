import pytest
import sqlite3
from src.domain.value_objects.agent_config import AgentConfig
from src.infrastructure.persistence.sqlite_agent_config_repository import (
    SqliteAgentConfigRepository,
    UserScopedAgentConfigRepository,
)

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

def test_user_scoped_agent_config_repository(repo):
    # 1. Global defaults
    repo.save(AgentConfig(role="architect", provider="gemini", model_name="gemini-1.5-pro"))
    repo.save(AgentConfig(role="judge", provider="openai", model_name="gpt-4o"))

    # 2. User 1 overrides only architect
    scoped_user1 = UserScopedAgentConfigRepository(repo, user_id="user-1")
    scoped_user1.save(AgentConfig(role="architect", provider="anthropic", model_name="claude-3-5-sonnet"))

    # 3. User 2 overrides only judge
    scoped_user2 = UserScopedAgentConfigRepository(repo, user_id="user-2")
    scoped_user2.save(AgentConfig(role="judge", provider="anthropic", model_name="claude-3-haiku"))

    # User 1 should get overridden architect, and default judge
    assert scoped_user1.find_by_role("architect").model_name == "claude-3-5-sonnet"
    assert scoped_user1.find_by_role("judge").model_name == "gpt-4o"

    # User 2 should get default architect, and overridden judge
    assert scoped_user2.find_by_role("architect").model_name == "gemini-1.5-pro"
    assert scoped_user2.find_by_role("judge").model_name == "claude-3-haiku"

    # Unscoped / default user should get system defaults
    scoped_default = UserScopedAgentConfigRepository(repo, user_id=None)
    assert scoped_default.find_by_role("architect").model_name == "gemini-1.5-pro"
    assert scoped_default.find_by_role("judge").model_name == "gpt-4o"
