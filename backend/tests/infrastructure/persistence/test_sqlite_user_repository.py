import pytest
import sqlite3
from src.domain.entities.user import User
from src.domain.exceptions import UserAlreadyExistsError
from src.infrastructure.persistence.sqlite_user_repository import SQLiteUserRepository


@pytest.fixture
def user_repo(tmp_path):
    db_file = str(tmp_path / "test_atenea.db")
    return SQLiteUserRepository(db_path=db_file)


@pytest.mark.asyncio
async def test_count_users_empty_on_fresh_db(user_repo):
    count = await user_repo.count_users()
    assert count == 0


@pytest.mark.asyncio
async def test_save_and_get_by_id(user_repo):
    user = User(
        id="usr-1",
        username="txus",
        password_hash="$argon2id$hash1",
        is_admin=True,
    )
    await user_repo.save(user)

    fetched = await user_repo.get_by_id("usr-1")
    assert fetched is not None
    assert fetched.id == "usr-1"
    assert fetched.username == "txus"
    assert fetched.password_hash == "$argon2id$hash1"
    assert fetched.is_admin is True
    assert fetched.is_active is True

    count = await user_repo.count_users()
    assert count == 1


@pytest.mark.asyncio
async def test_get_by_username_case_insensitive(user_repo):
    user = User(
        id="usr-2",
        username="john_doe",
        password_hash="$argon2id$hash2",
    )
    await user_repo.save(user)

    fetched = await user_repo.get_by_username("John_Doe")
    assert fetched is not None
    assert fetched.id == "usr-2"

    fetched_lower = await user_repo.get_by_username("john_doe")
    assert fetched_lower is not None
    assert fetched_lower.id == "usr-2"

    non_existent = await user_repo.get_by_username("nobody")
    assert non_existent is None


@pytest.mark.asyncio
async def test_save_duplicate_username_raises_error(user_repo):
    user1 = User(id="u1", username="admin", password_hash="h1")
    await user_repo.save(user1)

    user2 = User(id="u2", username="admin", password_hash="h2")
    with pytest.raises(UserAlreadyExistsError):
        await user_repo.save(user2)


@pytest.mark.asyncio
async def test_list_users(user_repo):
    u1 = User(id="u1", username="alice", password_hash="h1")
    u2 = User(id="u2", username="bob", password_hash="h2")
    await user_repo.save(u1)
    await user_repo.save(u2)

    users = await user_repo.list_users()
    assert len(users) == 2
    usernames = [u.username for u in users]
    assert "alice" in usernames
    assert "bob" in usernames


@pytest.mark.asyncio
async def test_delete_user(user_repo):
    u1 = User(id="u1", username="alice", password_hash="h1")
    await user_repo.save(u1)
    assert await user_repo.get_by_id("u1") is not None

    await user_repo.delete("u1")
    assert await user_repo.get_by_id("u1") is None


@pytest.mark.asyncio
async def test_save_and_fetch_token_version_and_deleted_at(user_repo):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    user = User(
        id="usr-versioned",
        username="version_user",
        password_hash="hash",
        token_version=42,
        deleted_at=now,
    )
    await user_repo.save(user)
    fetched = await user_repo.get_by_id("usr-versioned")
    assert fetched is not None
    assert fetched.token_version == 42
    assert fetched.deleted_at is not None


@pytest.mark.asyncio
async def test_user_repository_enables_wal_and_closes_every_connection(tmp_path, monkeypatch):
    import src.infrastructure.persistence.sqlite_base as sqlite_base_mod

    db_file = str(tmp_path / "tracked_users.db")
    repo = SQLiteUserRepository(db_path=db_file)

    with sqlite3.connect(db_file) as check_conn:
        mode = check_conn.execute("PRAGMA journal_mode").fetchone()[0]
    check_conn.close()
    assert str(mode).lower() == "wal"

    open_count = 0
    close_count = 0
    orig_connect = sqlite3.connect

    def _tracking_connect(*args, **kwargs):
        nonlocal open_count
        open_count += 1
        real_conn = orig_connect(*args, **kwargs)

        class _TrackedConn:
            def __getattr__(self, name):
                return getattr(real_conn, name)

            def close(self):
                nonlocal close_count
                close_count += 1
                return real_conn.close()

        return _TrackedConn()

    monkeypatch.setattr(sqlite_base_mod.sqlite3, "connect", _tracking_connect)

    await repo.save(User(id="u-wal-1", username="wal_user", password_hash="h1"))
    assert await repo.get_by_id("u-wal-1") is not None
    with pytest.raises(UserAlreadyExistsError):
        await repo.save(User(id="u-wal-2", username="wal_user", password_hash="h2"))

    assert open_count == 3
    assert close_count == 3



