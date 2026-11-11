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


def test_rag_top_k_and_min_score_persistence_per_user(repo):
    # Global default without explicit RAG params
    repo.save(AgentConfig(role="caliope", provider="gemini", model_name="gemini-2.5-flash"))

    scoped_user1 = UserScopedAgentConfigRepository(repo, user_id="user-1")
    scoped_user1.save(
        AgentConfig(
            role="caliope",
            provider="gemini",
            model_name="gemini-2.5-flash",
            rag_top_k=0,
            rag_min_score=0.65,
        )
    )

    scoped_user2 = UserScopedAgentConfigRepository(repo, user_id="user-2")
    scoped_user2.save(
        AgentConfig(
            role="caliope",
            provider="gemini",
            model_name="gemini-2.5-flash",
            rag_top_k=15,
            rag_min_score=0.45,
        )
    )

    found_u1 = scoped_user1.find_by_role("caliope")
    assert found_u1 is not None
    assert found_u1.rag_top_k == 0
    assert found_u1.rag_min_score == pytest.approx(0.65)

    found_u2 = scoped_user2.find_by_role("caliope")
    assert found_u2 is not None
    assert found_u2.rag_top_k == 15
    assert found_u2.rag_min_score == pytest.approx(0.45)

    found_default = repo.find_by_role("caliope", user_id="default")
    assert found_default is not None
    assert found_default.rag_top_k is None
    assert found_default.rag_min_score is None


def test_legacy_table_auto_migration_adds_rag_columns(tmp_path):
    db_path = tmp_path / "legacy_config.db"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE agent_configs (
                role TEXT NOT NULL,
                user_id TEXT NOT NULL DEFAULT 'default',
                provider TEXT NOT NULL,
                model_name TEXT NOT NULL,
                PRIMARY KEY (role, user_id)
            )
            """
        )
        conn.execute(
            "INSERT INTO agent_configs (role, user_id, provider, model_name) VALUES ('caliope', 'user-1', 'gemini', 'gemini-2.5-flash')"
        )
        conn.commit()

    # Initializing repository must auto-migrate rag_top_k and rag_min_score columns without data loss
    migrated_repo = SqliteAgentConfigRepository(str(db_path))
    existing = migrated_repo.find_by_role("caliope", user_id="user-1")
    assert existing is not None
    assert existing.provider == "gemini"
    assert existing.model_name == "gemini-2.5-flash"
    assert existing.rag_top_k is None
    assert existing.rag_min_score is None

    migrated_repo.save(
        AgentConfig(
            role="caliope",
            provider="gemini",
            model_name="gemini-2.5-flash",
            user_id="user-1",
            rag_top_k=8,
            rag_min_score=0.4,
        )
    )
    updated = migrated_repo.find_by_role("caliope", user_id="user-1")
    assert updated is not None
    assert updated.rag_top_k == 8
    assert updated.rag_min_score == pytest.approx(0.4)


