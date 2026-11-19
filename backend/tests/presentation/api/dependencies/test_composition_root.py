import asyncio
import threading
from unittest.mock import MagicMock
import pytest
from starlette.requests import HTTPConnection

from src.domain.ports.agent_catalog_repository import (
    IAgentCatalogRepository,
    ITopologyProvider,
)
from src.domain.ports.agent_config_repository import IAgentConfigRepository
from src.domain.ports.debate_repository import IDebateRepository
from src.domain.ports.document_parser import IDocumentParser
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.image_generator import IImageGenerator
from src.domain.ports.source_extractor import ISourceExtractor, SourceType
from src.infrastructure.image_generation.service import ImageGenerationService
from src.infrastructure.llm.registry import ConfiguredLLMProviderFactory, LLMProviderConfig
from src.infrastructure.persistence.postgres_user_repository import PostgreSQLUserRepository
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.infrastructure.persistence.sqlite_model_cache_repository import SqliteModelCacheRepository
from src.infrastructure.persistence.sqlite_user_repository import SQLiteUserRepository
from src.infrastructure.rag.obsidian_parser import ObsidianParser
from src.presentation.api.app import create_app
from src.presentation.api.config import Settings
from src.presentation.api.dependencies.auth import (
    get_agent_config_repository,
    get_auth_service,
    get_debate_repository,
    reset_auth_service,
)
from src.presentation.api.dependencies.learning import build_source_extractors
from src.presentation.api.dependencies.llm import (
    build_image_generator,
    build_llm_factory,
    build_llm_provider_config,
)
from src.presentation.api.dependencies.model_cache import get_model_cache_repository
from src.presentation.api.dependencies.rag import build_document_parser, get_document_store


def _make_sqlite_settings(tmp_path, database_url: str = "") -> Settings:
    return Settings(
        sqlite_db_path=tmp_path / "sqlite.db",
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
        database_url=database_url,
    )


def test_composition_root_sqlite_default(monkeypatch, tmp_path):
    reset_auth_service()
    settings = _make_sqlite_settings(tmp_path)
    monkeypatch.setattr("src.presentation.api.dependencies.auth.get_settings", lambda: settings)

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app.state = MagicMock()
    mock_conn.app.state.auth_service = None
    mock_conn.app.state.db_pool = None

    try:
        service = get_auth_service(mock_conn)
        assert isinstance(service._user_repo, SQLiteUserRepository)
        assert isinstance(service._debate_repo, SqliteDebateRepository)
        assert isinstance(service._agent_config_repo, SqliteAgentConfigRepository)
        assert (tmp_path / "sqlite.db").exists()
    finally:
        reset_auth_service()


def test_composition_root_repositories_bound_to_configured_sqlite_path(monkeypatch, tmp_path):
    settings = _make_sqlite_settings(tmp_path)
    expected_db = str(tmp_path / "sqlite.db")

    debate_repo = get_debate_repository(settings)
    agent_cfg_repo = get_agent_config_repository(settings)
    assert isinstance(debate_repo, IDebateRepository)
    assert isinstance(debate_repo, SqliteDebateRepository)
    assert debate_repo._db_path == expected_db

    assert isinstance(agent_cfg_repo, IAgentConfigRepository)
    assert isinstance(agent_cfg_repo, SqliteAgentConfigRepository)
    assert agent_cfg_repo._db_path == expected_db

    get_model_cache_repository.cache_clear()
    monkeypatch.setattr("src.presentation.api.dependencies.model_cache.get_settings", lambda: settings)
    try:
        model_cache_repo = get_model_cache_repository()
        assert isinstance(model_cache_repo, SqliteModelCacheRepository)
        assert model_cache_repo._db_path == expected_db
    finally:
        get_model_cache_repository.cache_clear()


def test_composition_root_postgres_wired(monkeypatch, tmp_path):
    reset_auth_service()
    settings = _make_sqlite_settings(
        tmp_path,
        database_url="postgresql://user:pass@localhost:5432/atenea",
    )
    monkeypatch.setattr("src.presentation.api.dependencies.auth.get_settings", lambda: settings)

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app.state = MagicMock()
    mock_conn.app.state.auth_service = None
    mock_conn.app.state.db_pool = MagicMock()

    try:
        service = get_auth_service(mock_conn)
        assert isinstance(service._user_repo, PostgreSQLUserRepository)
        assert isinstance(service._debate_repo, SqliteDebateRepository)
        assert isinstance(service._agent_config_repo, SqliteAgentConfigRepository)
    finally:
        reset_auth_service()


def test_composition_root_postgres_missing_pool_raises_fail_fast(monkeypatch, tmp_path):
    reset_auth_service()
    settings = _make_sqlite_settings(
        tmp_path,
        database_url="postgresql://user:pass@localhost:5432/atenea",
    )
    monkeypatch.setattr("src.presentation.api.dependencies.auth.get_settings", lambda: settings)

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app.state = MagicMock()
    mock_conn.app.state.auth_service = None
    mock_conn.app.state.db_pool = None

    try:
        with pytest.raises(RuntimeError) as exc:
            get_auth_service(mock_conn)
        assert "DATABASE_URL is configured for PostgreSQL, but no database pool" in str(exc.value)
    finally:
        reset_auth_service()


def test_composition_root_prefers_app_state_auth_service(tmp_path):
    settings = _make_sqlite_settings(tmp_path)
    custom_auth = MagicMock()
    app = create_app(settings=settings, auth_service=custom_auth)

    assert app.state.settings is settings
    assert app.state.auth_service is custom_auth

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app = app
    assert get_auth_service(mock_conn) is custom_auth


@pytest.mark.asyncio
async def test_document_store_singleton_cached_on_app_state(monkeypatch, tmp_path):
    settings = _make_sqlite_settings(tmp_path)
    app = create_app(settings=settings)
    main_tid = threading.get_ident()
    init_threads: list[int] = []
    created_instances: list[MagicMock] = []

    def _fake_store(*args, **kwargs):
        init_threads.append(threading.get_ident())
        inst = MagicMock(spec=IDocumentStore)
        created_instances.append(inst)
        return inst

    monkeypatch.setattr("src.presentation.api.dependencies.rag.ChromaDBDocumentStore", _fake_store)

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app = app

    s1, s2, s3 = await asyncio.gather(
        get_document_store(mock_conn),
        get_document_store(mock_conn),
        get_document_store(mock_conn),
    )

    assert len(created_instances) == 1
    assert s1 is s2 is s3 is app.state.document_store
    assert init_threads == [t for t in init_threads if t != main_tid]


def test_create_app_accepts_preconfigured_document_store(tmp_path):
    settings = _make_sqlite_settings(tmp_path)
    custom_store = MagicMock(spec=IDocumentStore)
    app = create_app(settings=settings, document_store=custom_store)
    assert app.state.document_store is custom_store


def test_composition_root_wires_agent_catalog_topology_and_task_limit(monkeypatch, tmp_path):
    settings = _make_sqlite_settings(tmp_path)
    app = create_app(settings=settings)

    assert isinstance(app.state.agent_catalog, IAgentCatalogRepository)
    assert isinstance(app.state.topology_provider, ITopologyProvider)
    assert app.state.topology_provider.get_topology().supervisor

    agent_cfg_repo = get_agent_config_repository(settings)
    assert getattr(agent_cfg_repo, "_agent_catalog", None) is not None

    monkeypatch.setenv("TASK_PROMPT_MAX_LENGTH", "2048")
    custom_settings = Settings(
        sqlite_db_path=tmp_path / "sqlite2.db",
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
    )
    assert custom_settings.task_prompt_max_length == 2048


def test_composition_root_wires_ports_and_llm_image_config(monkeypatch, tmp_path):
    monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    settings = Settings(
        sqlite_db_path=tmp_path / "sqlite.db",
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
        gemini_api_key="gem-root-key",
        openai_api_key="oai-root-key",
        image_generation_provider="imagen",
    )
    app = create_app(settings=settings)

    assert isinstance(app.state.llm_config, LLMProviderConfig)
    assert app.state.llm_config.gemini_api_key == "gem-root-key"
    assert app.state.llm_config.openai_api_key == "oai-root-key"

    assert isinstance(app.state.image_generator, IImageGenerator)
    assert isinstance(app.state.image_generator, ImageGenerationService)
    assert app.state.image_generator.get_provider_name() == "imagen"

    assert isinstance(app.state.document_parser, IDocumentParser)
    assert isinstance(app.state.document_parser, ObsidianParser)

    assert set(app.state.source_extractors.keys()) == {
        SourceType.PDF,
        SourceType.URL,
        SourceType.MARKDOWN,
        SourceType.IMAGE,
    }
    assert all(isinstance(ext, ISourceExtractor) for ext in app.state.source_extractors.values())

    factory = build_llm_factory(settings)
    assert isinstance(factory, ConfiguredLLMProviderFactory)
    assert factory.is_configured("openai") is True
    assert build_llm_provider_config(settings) == app.state.llm_config
    assert build_image_generator(settings).get_provider_name() == "imagen"
    assert isinstance(build_document_parser(), ObsidianParser)
    assert len(build_source_extractors()) == 4


def test_create_app_accepts_injected_dip_overrides(tmp_path):
    settings = _make_sqlite_settings(tmp_path)
    custom_parser = MagicMock(spec=IDocumentParser)
    custom_img = MagicMock(spec=IImageGenerator)
    custom_extractors = {SourceType.PDF: MagicMock(spec=ISourceExtractor)}
    custom_cfg = LLMProviderConfig(gemini_api_key="override-key")

    app = create_app(
        settings=settings,
        llm_config=custom_cfg,
        image_generator=custom_img,
        document_parser=custom_parser,
        source_extractors=custom_extractors,
    )

    assert app.state.llm_config is custom_cfg
    assert app.state.image_generator is custom_img
    assert app.state.document_parser is custom_parser
    assert app.state.source_extractors is custom_extractors
