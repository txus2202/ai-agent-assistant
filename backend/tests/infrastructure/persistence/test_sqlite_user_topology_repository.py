"""
Persistence & YAML adapter tests for UserTopologyConfig and review_rounds.

Layer: Infrastructure
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.services.auth_service import AuthService
from src.domain.entities.user import User
from src.domain.value_objects.user_topology_config import UserTopologyConfig
from src.infrastructure.config.yaml_topology_provider import load_topology
from src.infrastructure.persistence.sqlite_user_topology_repository import (
    SqliteUserTopologyRepository,
)


def test_sqlite_user_topology_crud_and_user_isolation(tmp_path: Path):
    db_file = str(tmp_path / "topologies.db")
    repo = SqliteUserTopologyRepository(db_file)

    assert repo.find_by_user_id("u1") is None

    cfg1 = UserTopologyConfig(
        user_id="u1",
        interpreters=(),
        proposers=("MakerA", "DoerB"),
        reviewers=("Checker",),
        evaluators=("Checker",),
        implementers=("DoerA",),
        review_rounds=3,
    )
    cfg2 = UserTopologyConfig(
        user_id="u2",
        interpreters=("Reader",),
        proposers=("MakerB",),
        reviewers=(),
        evaluators=(),
        implementers=(),
        review_rounds=0,
    )
    repo.save(cfg1)
    repo.save(cfg2)

    loaded1 = repo.find_by_user_id("u1")
    loaded2 = repo.find_by_user_id("u2")
    assert loaded1 == cfg1
    assert loaded2 == cfg2

    # Upsert u1
    updated1 = UserTopologyConfig(
        user_id="u1",
        interpreters=("Reader",),
        proposers=("MakerA",),
        reviewers=(),
        evaluators=("Checker",),
        implementers=(),
        review_rounds=4,
    )
    repo.save(updated1)
    assert repo.find_by_user_id("u1") == updated1
    assert repo.find_by_user_id("u2") == cfg2

    # Delete u1 only
    repo.delete_by_user_id("u1")
    assert repo.find_by_user_id("u1") is None
    assert repo.find_by_user_id("u2") == cfg2


@pytest.mark.anyio
async def test_auth_service_hard_delete_purges_user_topology(tmp_path: Path):
    db_file = str(tmp_path / "purge.db")
    top_repo = SqliteUserTopologyRepository(db_file)
    top_repo.save(
        UserTopologyConfig(
            user_id="victim-id",
            proposers=("MakerA",),
            review_rounds=2,
        )
    )

    admin = User(id="admin-id", username="admin", password_hash="h", is_admin=True, is_active=True)
    victim = User(id="victim-id", username="victim", password_hash="h", is_admin=False, is_active=True)

    mock_user_repo = MagicMock()
    mock_user_repo.get_by_id = AsyncMock(return_value=victim)
    mock_user_repo.delete = AsyncMock(return_value=True)

    auth_svc = AuthService(
        user_repo=mock_user_repo,
        hasher=MagicMock(),
        token_service=MagicMock(),
        delete_strategy="hard",
        user_topology_repo=top_repo,
    )

    result = await auth_svc.delete_user(admin, "victim-id")
    assert result == "hard"
    assert top_repo.find_by_user_id("victim-id") is None


def test_load_topology_parses_review_rounds_from_root_yaml():
    top = load_topology()
    assert top.review_rounds == 1

