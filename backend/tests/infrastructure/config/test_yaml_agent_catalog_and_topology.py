"""
Infrastructure Tests — YAML Agent Catalog Repository & YAML Topology Provider.

Validates PyYAML parsing, filesystem resolution (AGENTS_FILE, TOPOLOGY_FILE),
structural consistency of shipped root YAML catalogs, and pure port injection into
infrastructure consumers (SqliteAgentConfigRepository, WakeWordService, LocalAudioService).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.domain.ports.agent_catalog_repository import (
    IAgentCatalogRepository,
    ITopologyProvider,
)
from src.domain.value_objects.agent_config import AgentConfig
from src.infrastructure.audio.local_audio_service import LocalAudioService
from src.infrastructure.audio.wake_word_service import WakeWordService
from src.infrastructure.config.yaml_agent_catalog import (
    InMemoryAgentCatalogRepository,
    YamlAgentCatalogRepository,
    load_profiles_from_file,
)
from src.infrastructure.config.yaml_topology_provider import (
    YamlTopologyProvider,
    load_topology,
)
from src.infrastructure.persistence.sqlite_agent_config_repository import (
    SqliteAgentConfigRepository,
)


VALID_CATALOG = """\
agents:
  - id: sup_id
    display_name: Boss
    description: Generic supervisor used in catalog tests.
    color_hex: "#ffaa00"
    system_prompt: You are Boss.
    is_supervisor: true
  - id: alpha_id
    display_name: Alpha
    description: First generic agent used in catalog tests.
    color_hex: "#aabbcc"
    system_prompt: |
      You are Alpha.
      Second line of the prompt.
    uses_rag: true
    rag_filter:
      type: spec
      status: implemented
    phonetic_aliases: [alfa, "al fa"]
    supports_hitl: false
  - id: beta_id
    display_name: Beta
    description: Second generic agent used in catalog tests.
    color_hex: "#ddeeff"
    system_prompt: You are Beta.
    can_ingest_documents: true
    tools: [code_viewer, image_viewer]
"""


def _write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


class TestYamlAgentCatalogRepository:
    def test_implements_port_and_loads_from_valid_file(self, tmp_path: Path):
        catalog_path = _write(tmp_path / "agents.yaml", VALID_CATALOG)
        repo = YamlAgentCatalogRepository(catalog_path)

        assert isinstance(repo, IAgentCatalogRepository)
        profiles = repo.get_all_profiles()
        assert [p.id for p in profiles] == ["sup_id", "alpha_id", "beta_id"]

        alpha = repo.get_profile("alfa")
        assert alpha.id == "alpha_id"
        assert alpha.uses_rag is True
        assert alpha.rag_filter is not None
        assert alpha.rag_filter.type == "spec"
        assert alpha.rag_filter.status == "implemented"
        assert alpha.supports_hitl is False
        assert repo.get_profile("beta_id").supports_image_generation is True

    def test_instances_have_no_shared_mutable_state(self, tmp_path: Path):
        p = _write(tmp_path / "agents.yaml", VALID_CATALOG)
        repo_a = YamlAgentCatalogRepository(p)
        repo_b = YamlAgentCatalogRepository(p)

        custom = SubAgentProfile(
            id="extra_id",
            display_name="Extra",
            description="Dynamic isolated agent",
            color_hex="#000000",
            system_prompt="Extra prompt",
        )
        repo_a.register_profile(custom)

        assert repo_a.get_profile("extra_id") is custom
        with pytest.raises(KeyError):
            repo_b.get_profile("extra_id")

        assert repo_a.unregister_profile("extra_id") is True
        assert repo_a.unregister_profile("extra_id") is False

    def test_validation_errors_on_malformed_catalogs(self, tmp_path: Path):
        no_sup = _write(
            tmp_path / "nosup.yaml",
            "agents:\n  - id: a\n    display_name: A\n    description: Desc A\n    color_hex: '#111111'\n    system_prompt: Prompt A\n",
        )
        with pytest.raises(ValueError, match="supervisor"):
            load_profiles_from_file(no_sup)

        with pytest.raises(FileNotFoundError):
            load_profiles_from_file(tmp_path / "missing.yaml")

        missing_desc = _write(
            tmp_path / "nodesc.yaml",
            "agents:\n  - id: a\n    display_name: A\n    color_hex: '#111111'\n    system_prompt: Prompt A\n",
        )
        with pytest.raises(ValueError, match="description"):
            load_profiles_from_file(missing_desc)

        dup = _write(
            tmp_path / "dup.yaml",
            "agents:\n"
            "  - id: dup_id\n    display_name: A\n    description: D1\n    color_hex: '#111111'\n    system_prompt: P1\n"
            "  - id: dup_id\n    display_name: B\n    description: D2\n    color_hex: '#222222'\n    system_prompt: P2\n",
        )
        with pytest.raises(ValueError, match="dup_id"):
            load_profiles_from_file(dup)

        no_agents = _write(tmp_path / "empty.yaml", "version: 1\n")
        with pytest.raises(ValueError, match="agents"):
            load_profiles_from_file(no_agents)

    def test_honors_agents_file_env_var(self, tmp_path: Path, monkeypatch):
        path = _write(tmp_path / "custom_agents.yaml", VALID_CATALOG)
        monkeypatch.setenv("AGENTS_FILE", str(path))
        repo = YamlAgentCatalogRepository()
        assert {p.id for p in repo.get_all_profiles()} == {"sup_id", "alpha_id", "beta_id"}

        monkeypatch.setenv("AGENTS_FILE", str(tmp_path / "nope.yaml"))
        with pytest.raises(FileNotFoundError):
            YamlAgentCatalogRepository()


class TestYamlTopologyProvider:
    def test_loads_and_caches_topology_and_honors_env_var(self, tmp_path: Path, monkeypatch):
        agents_path = _write(tmp_path / "agents.yaml", VALID_CATALOG)
        top_path = _write(
            tmp_path / "topology.yaml",
            'version: "2.0"\nsupervisor: "Boss"\ninterpreters:\n  - "Alpha"\nproposers:\n  - "Beta"\n',
        )
        catalog = YamlAgentCatalogRepository(agents_path)
        provider = YamlTopologyProvider(agent_catalog=catalog, topology_path=top_path)

        assert isinstance(provider, ITopologyProvider)
        first = provider.get_topology()
        second = provider.get_topology()
        assert first is second
        assert first.supervisor == "Boss"
        assert first.interpreters == ("Alpha",)
        assert first.proposers == ("Beta",)
        assert first.reviewers == ()

        monkeypatch.setenv("TOPOLOGY_FILE", str(top_path))
        loaded_env = load_topology(agent_catalog=catalog)
        assert loaded_env == first

    def test_invalid_topology_raises(self, tmp_path: Path):
        agents_path = _write(tmp_path / "agents.yaml", VALID_CATALOG)
        catalog = YamlAgentCatalogRepository(agents_path)

        no_sup = _write(tmp_path / "bad_top.yaml", 'interpreters: ["Alpha"]\n')
        with pytest.raises(ValueError, match="supervisor"):
            load_topology(no_sup, agent_catalog=catalog)

        unknown_agent = _write(tmp_path / "unknown.yaml", 'supervisor: "Boss"\nproposers: ["Ghost"]\n')
        with pytest.raises(KeyError):
            load_topology(unknown_agent, agent_catalog=catalog)

        with pytest.raises(FileNotFoundError):
            load_topology(tmp_path / "missing.yaml", agent_catalog=catalog)


class TestShippedCatalogAndTopologyConsistency:
    def test_shipped_root_catalog_and_topology_are_mutually_consistent(self):
        catalog = YamlAgentCatalogRepository()
        provider = YamlTopologyProvider(agent_catalog=catalog)
        top = provider.get_topology()
        top.validate(catalog)

        profiles = catalog.get_all_profiles()
        assert len({p.id for p in profiles}) == len(profiles)
        assert len({p.display_name.lower() for p in profiles}) == len(profiles)
        for profile in profiles:
            assert profile.color_hex.startswith("#")
            assert len(profile.color_hex) == 7
            if not profile.uses_rag:
                assert profile.rag_filter is None


class TestInfrastructureConsumersUseInjectedCatalogPort:
    def test_sqlite_agent_config_repo_resolves_alias_via_injected_catalog(self, tmp_path: Path):
        catalog = InMemoryAgentCatalogRepository(
            profiles=[
                SubAgentProfile(
                    id="custom_role",
                    display_name="CustomDisplay",
                    description="Desc",
                    color_hex="#123456",
                    system_prompt="Prompt",
                )
            ]
        )
        repo = SqliteAgentConfigRepository(str(tmp_path / "cfg.db"), agent_catalog=catalog)
        repo.save(AgentConfig(role="custom_role", provider="gemini", model_name="gemini-2.5-flash"))

        found = repo.find_by_role("CustomDisplay")
        assert found is not None
        assert found.model_name == "gemini-2.5-flash"

    def test_wake_word_and_local_audio_use_injected_catalog_without_disk(self):
        catalog = InMemoryAgentCatalogRepository(
            profiles=[
                SubAgentProfile(
                    id="synthetic_id",
                    display_name="Orion",
                    description="Synthetic agent",
                    color_hex="#112233",
                    system_prompt="Prompt",
                    phonetic_aliases=("oryon",),
                )
            ]
        )
        ww = WakeWordService(agent_catalog=catalog)
        assert "orion" in ww._agent_triggers
        assert ww._agent_triggers["oryon"] == ("synthetic_id", "Orion")

        with patch("src.infrastructure.audio.local_audio_service.av.open"):
            audio = LocalAudioService(
                whisper_model_size="base",
                kokoro_model_path=Path("dummy.onnx"),
                kokoro_voices_path=Path("dummy.bin"),
                kokoro_voice_name="ef_dora",
                agent_catalog=catalog,
            )
        prompt = audio._build_initial_prompt()
        assert "Nombres de agentes: Orion." in prompt

