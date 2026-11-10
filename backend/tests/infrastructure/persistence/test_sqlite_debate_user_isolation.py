import pytest
from src.domain.value_objects.debate_record import DebateRecord
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository


@pytest.fixture
def debate_repo(tmp_path):
    db_file = str(tmp_path / "test_debates_isolation.db")
    return SqliteDebateRepository(db_path=db_file)


def test_debate_creation_and_filtering_by_user_id(debate_repo):
    d1 = DebateRecord(id="d-1", user_request="Design microservice", user_id="user_alice")
    d2 = DebateRecord(id="d-2", user_request="Review security", user_id="user_bob")
    d3 = DebateRecord(id="d-3", user_request="Deploy to k8s", user_id="user_alice")

    debate_repo.create(d1)
    debate_repo.create(d2)
    debate_repo.create(d3)

    # Alice should see d1 and d3
    alice_debates = debate_repo.find_all(user_id="user_alice")
    assert len(alice_debates) == 2
    alice_ids = [d.id for d in alice_debates]
    assert "d-1" in alice_ids
    assert "d-3" in alice_ids
    assert "d-2" not in alice_ids

    # Bob should only see d2
    bob_debates = debate_repo.find_all(user_id="user_bob")
    assert len(bob_debates) == 1
    assert bob_debates[0].id == "d-2"


def test_find_by_id_restricted_to_owner(debate_repo):
    d1 = DebateRecord(id="d-1", user_request="Confidential architecture", user_id="user_alice")
    debate_repo.create(d1)

    # Alice can find d1
    found_alice = debate_repo.find_by_id("d-1", user_id="user_alice")
    assert found_alice is not None
    assert found_alice.id == "d-1"

    # Bob cannot access Alice's debate
    found_bob = debate_repo.find_by_id("d-1", user_id="user_bob")
    assert found_bob is None

