"""
RED tests for SQLiteAgentRepository and SQLiteTaskRepository.

Spec: obsidian_vault/docs/features/feature_sqlite_repositories.md
Phase: 2 | Layer: Infrastructure

The defining characteristic tested here — absent from InMemory tests — is
DISK PERSISTENCE: data written by one repository instance must be readable
by a separate instance opened against the same file.

All tests use pytest's `tmp_path` fixture to avoid touching real files.
"""
import uuid
from pathlib import Path


from src.domain.entities.agent import Agent, AgentStatus
from src.domain.entities.task import Task
from src.domain.ports.agent_repository import IAgentRepository
from src.infrastructure.persistence.sqlite_agent_repository import (
    SqliteAgentRepository,
)
from src.infrastructure.persistence.sqlite_task_repository import (
    SqliteTaskRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(provider: str = "gemini") -> Agent:
    return Agent(
        name="Annotator",
        role="Documentation specialist",
        provider=provider,
        model_name="gemini-3.6-flash",
    )


def _make_task(agent_id: uuid.UUID, prompt: str = "Explain the system.") -> Task:
    return Task(prompt=prompt, agent_id=agent_id)


# ===========================================================================
# SQLiteAgentRepository
# ===========================================================================

class TestSqliteAgentRepository:

    # -----------------------------------------------------------------------
    # Scenario 1: Persistence across connections (key differentiator)
    # -----------------------------------------------------------------------

    def test_save_persists_to_disk_and_survives_reconnection(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test.db"
        agent = _make_agent()

        # Write with first instance
        repo_write = SqliteAgentRepository(db_path=str(db_file))
        repo_write.save(agent)

        # Read with a brand-new instance — proves disk persistence
        repo_read = SqliteAgentRepository(db_path=str(db_file))
        found = repo_read.find_by_id(agent.id)

        assert found is not None
        assert found.id == agent.id
        assert found.name == agent.name
        assert found.provider == agent.provider
        assert found.model_name == agent.model_name
        assert found.status == agent.status

    # -----------------------------------------------------------------------
    # Scenario 2: Implements IAgentRepository (LSP)
    # -----------------------------------------------------------------------

    def test_implements_iagent_repository(self, tmp_path: Path) -> None:
        repo: IAgentRepository = SqliteAgentRepository(db_path=str(tmp_path / "test.db"))
        agent = _make_agent()

        repo.save(agent)
        all_agents = repo.find_all()
        found = repo.find_by_id(agent.id)
        repo.delete(agent.id)

        assert len(all_agents) == 1
        assert found is not None
        assert repo.find_by_id(agent.id) is None

    # -----------------------------------------------------------------------
    # Scenario 3: Delete removes from disk
    # -----------------------------------------------------------------------

    def test_delete_removes_agent_from_disk(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test.db"
        agent = _make_agent()

        repo = SqliteAgentRepository(db_path=str(db_file))
        repo.save(agent)
        repo.delete(agent.id)

        # New connection — data must be gone
        repo2 = SqliteAgentRepository(db_path=str(db_file))
        assert repo2.find_by_id(agent.id) is None

    # -----------------------------------------------------------------------
    # Scenario 4: save is upsert — updated status survives reconnection
    # -----------------------------------------------------------------------

    def test_upsert_status_survives_reconnection(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test.db"
        agent = _make_agent()

        repo1 = SqliteAgentRepository(db_path=str(db_file))
        repo1.save(agent)

        agent.status = AgentStatus.ERROR
        repo1.save(agent)  # update

        repo2 = SqliteAgentRepository(db_path=str(db_file))
        found = repo2.find_by_id(agent.id)

        assert found is not None
        assert found.status == AgentStatus.ERROR

    # -----------------------------------------------------------------------
    # Extra: find_all returns empty list for new DB
    # -----------------------------------------------------------------------

    def test_find_all_returns_empty_for_new_db(self, tmp_path: Path) -> None:
        repo = SqliteAgentRepository(db_path=str(tmp_path / "test.db"))
        assert repo.find_all() == []

    # -----------------------------------------------------------------------
    # Extra: delete is idempotent
    # -----------------------------------------------------------------------

    def test_delete_non_existent_agent_does_not_raise(self, tmp_path: Path) -> None:
        repo = SqliteAgentRepository(db_path=str(tmp_path / "test.db"))
        repo.delete(uuid.uuid4())  # must NOT raise


# ===========================================================================
# SQLiteTaskRepository
# ===========================================================================

class TestSqliteTaskRepository:

    # -----------------------------------------------------------------------
    # Scenario 5: save + find_by_id persists to disk
    # -----------------------------------------------------------------------

    def test_save_persists_task_to_disk(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test.db"
        agent_id = uuid.uuid4()
        task = _make_task(agent_id)

        repo_write = SqliteTaskRepository(db_path=str(db_file))
        repo_write.save(task)

        repo_read = SqliteTaskRepository(db_path=str(db_file))
        found = repo_read.find_by_id(task.id)

        assert found is not None
        assert found.id == task.id
        assert found.prompt == task.prompt
        assert found.agent_id == agent_id
        assert found.status == task.status

    # -----------------------------------------------------------------------
    # Scenario 6: find_by_agent_id scopes correctly
    # -----------------------------------------------------------------------

    def test_find_by_agent_id_returns_only_tasks_for_that_agent(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test.db"
        agent_a = uuid.uuid4()
        agent_b = uuid.uuid4()

        repo = SqliteTaskRepository(db_path=str(db_file))
        repo.save(_make_task(agent_a, "Task A1"))
        repo.save(_make_task(agent_a, "Task A2"))
        repo.save(_make_task(agent_b, "Task B1"))

        results = repo.find_by_agent_id(agent_a)

        assert len(results) == 2
        assert all(t.agent_id == agent_a for t in results)

    # -----------------------------------------------------------------------
    # Scenario 7: Completed task status and result survive reconnection
    # -----------------------------------------------------------------------

    def test_completed_task_status_and_result_survive_reconnection(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test.db"
        agent_id = uuid.uuid4()
        task = _make_task(agent_id)
        task.mark_as_running()
        task.mark_as_completed(result="The answer is 42")

        repo1 = SqliteTaskRepository(db_path=str(db_file))
        repo1.save(task)

        repo2 = SqliteTaskRepository(db_path=str(db_file))
        found = repo2.find_by_id(task.id)

        assert found is not None
        assert found.status.value == "completed"
        assert found.result == "The answer is 42"

    # -----------------------------------------------------------------------
    # Extra: dependencies are serialized and restored correctly
    # -----------------------------------------------------------------------

    def test_task_dependencies_survive_reconnection(self, tmp_path: Path) -> None:
        db_file = tmp_path / "test.db"
        agent_id = uuid.uuid4()
        dep_1 = uuid.uuid4()
        dep_2 = uuid.uuid4()
        task = Task(prompt="Generate diagram.", agent_id=agent_id, dependencies=[dep_1, dep_2])

        repo1 = SqliteTaskRepository(db_path=str(db_file))
        repo1.save(task)

        repo2 = SqliteTaskRepository(db_path=str(db_file))
        found = repo2.find_by_id(task.id)

        assert found is not None
        assert dep_1 in found.dependencies
        assert dep_2 in found.dependencies

    # -----------------------------------------------------------------------
    # Extra: created_at timezone is preserved
    # -----------------------------------------------------------------------

    def test_created_at_is_utc_aware_after_deserialization(self, tmp_path: Path) -> None:
        from datetime import timezone
        db_file = tmp_path / "test.db"
        agent_id = uuid.uuid4()
        task = _make_task(agent_id)

        repo = SqliteTaskRepository(db_path=str(db_file))
        repo.save(task)

        found = repo.find_by_id(task.id)
        assert found is not None
        assert found.created_at.tzinfo is not None
        assert found.created_at.tzinfo == timezone.utc
