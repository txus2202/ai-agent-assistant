"""
Tests — SubAgentProfile, dynamic registry and external agent catalog.

Layer: Domain

These tests are intentionally agnostic of the council currently shipped in
``agents.yaml``: they only use generic agent names (alpha, beta, ...). The one
integration test against the real catalog asserts structural invariants only.

Scenarios:
  1. The registry always contains exactly one built-in supervisor
  2. Profiles are retrievable by id, display_name, alias (case/accents-insensitive)
  3. register_profile / unregister_profile add and remove agents at runtime
  4. Profiles load from an external YAML catalog (and validate it)
  5. reset_default_profiles() honours the AGENTS_FILE environment variable
  6. The real catalog is consistent with the real topology
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.agents.sub_agent_profiles import (
    SubAgentProfile,
    get_all_profiles,
    get_profile,
    load_profiles_from_file,
    register_profile,
    reset_default_profiles,
    unregister_profile,
)
from src.domain.agents.supervisor_events import (
    EventType,
    HITLDecision,
    HITLResponse,
    SupervisorEvent,
)


def _profile(agent_id: str, name: str, **kwargs) -> SubAgentProfile:
    return SubAgentProfile(
        id=agent_id,
        display_name=name,
        description=f"Generic test agent {name} used for registry tests.",
        color_hex="#112233",
        system_prompt=f"You are {name}. " + "Generic instructions. " * 5,
        **kwargs,
    )


def _write_catalog(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "agents.yaml"
    path.write_text(body, encoding="utf-8")
    return path


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
"""


@pytest.fixture(autouse=True)
def clean_registry():
    reset_default_profiles()
    yield
    reset_default_profiles()


class TestSupervisorProfileInRegistry:
    def test_sub_agent_profiles_module_has_no_builtin_supervisor_constant(self):
        import src.domain.agents.sub_agent_profiles as mod
        assert not hasattr(mod, "BUILTIN_SUPERVISOR")

    def test_registry_has_supervisor_loaded_from_catalog(self):
        supervisors = [p for p in get_all_profiles() if p.is_supervisor]
        assert len(supervisors) >= 1

    def test_supervisor_is_retrievable_by_its_id_and_display_name(self):
        sup = next(p for p in get_all_profiles() if p.is_supervisor)
        assert get_profile(sup.id) is sup
        assert get_profile(sup.display_name) is sup

    def test_supervisor_prompt_does_not_enumerate_other_agents(self):
        sup = next(p for p in get_all_profiles() if p.is_supervisor)
        for other in get_all_profiles():
            if other.id != sup.id:
                assert other.display_name not in sup.system_prompt


class TestDynamicRegistry:
    def test_register_makes_profile_retrievable_by_id_name_and_alias(self):
        register_profile(_profile("alpha_id", "Álpha", phonetic_aliases=("alfa",)))

        assert get_profile("alpha_id").display_name == "Álpha"
        assert get_profile("Álpha").id == "alpha_id"
        assert get_profile("alpha").id == "alpha_id"  # accent-insensitive
        assert get_profile("ALFA").id == "alpha_id"  # alias, case-insensitive

    def test_register_same_id_replaces_previous_profile(self):
        register_profile(_profile("alpha_id", "Alpha"))
        count = len(get_all_profiles())
        register_profile(_profile("alpha_id", "Alpha Renamed"))

        assert len(get_all_profiles()) == count
        assert get_profile("alpha_id").display_name == "Alpha Renamed"

    def test_unregister_removes_agent_and_keeps_others(self):
        register_profile(_profile("alpha_id", "Alpha"))
        register_profile(_profile("beta_id", "Beta"))

        assert unregister_profile("Alpha") is True

        with pytest.raises(KeyError):
            get_profile("alpha_id")
        assert get_profile("beta_id").display_name == "Beta"

    def test_unregister_unknown_returns_false(self):
        assert unregister_profile("does_not_exist") is False

    def test_unknown_identifier_raises_key_error(self):
        with pytest.raises(KeyError):
            get_profile("non_existent_agent")

    def test_registration_order_is_preserved(self):
        register_profile(_profile("alpha_id", "Alpha"))
        register_profile(_profile("beta_id", "Beta"))
        ids = [p.id for p in get_all_profiles()]
        assert ids.index("alpha_id") < ids.index("beta_id")


class TestSubAgentProfileModel:
    def test_profile_is_frozen_immutable(self):
        profile = _profile("alpha_id", "Alpha")
        with pytest.raises((AttributeError, TypeError)):
            profile.system_prompt = "mutated"  # type: ignore[misc]

    def test_defaults(self):
        profile = _profile("alpha_id", "Alpha")
        assert profile.uses_rag is False
        assert profile.rag_filter is None
        assert profile.phonetic_aliases == ()
        assert profile.supports_hitl is True
        assert profile.is_supervisor is False
        assert profile.can_ingest_documents is False

    def test_name_property_matches_display_name(self):
        assert _profile("alpha_id", "Alpha").name == "Alpha"


class TestExternalCatalog:
    def test_load_profiles_from_valid_file(self, tmp_path: Path):
        profiles = load_profiles_from_file(_write_catalog(tmp_path, VALID_CATALOG))

        assert [p.id for p in profiles] == ["sup_id", "alpha_id", "beta_id"]
        sup, alpha, beta = profiles
        assert sup.is_supervisor is True
        assert sup.display_name == "Boss"
        assert alpha.display_name == "Alpha"
        assert alpha.uses_rag is True
        assert alpha.rag_filter is not None
        assert alpha.rag_filter.type == "spec"
        assert alpha.rag_filter.status == "implemented"
        assert alpha.phonetic_aliases == ("alfa", "al fa")
        assert alpha.supports_hitl is False
        assert "Second line of the prompt." in alpha.system_prompt
        assert beta.can_ingest_documents is True
        assert beta.uses_rag is False
        assert beta.rag_filter is None

    def test_catalog_without_supervisor_raises_value_error(self, tmp_path: Path):
        body = """\
agents:
  - id: alpha_id
    display_name: Alpha
    description: Generic agent without supervisor flag.
    color_hex: "#aabbcc"
    system_prompt: You are Alpha.
"""
        path = _write_catalog(tmp_path, body)
        with pytest.raises(ValueError, match="supervisor"):
            load_profiles_from_file(path)

    def test_missing_file_raises_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_profiles_from_file(tmp_path / "nope.yaml")

    def test_missing_required_field_raises_value_error(self, tmp_path: Path):
        body = """\
agents:
  - id: alpha_id
    display_name: Alpha
    color_hex: "#aabbcc"
    system_prompt: You are Alpha.
"""
        path = _write_catalog(tmp_path, body)
        with pytest.raises(ValueError, match="description"):
            load_profiles_from_file(path)

    def test_duplicate_ids_raise_value_error(self, tmp_path: Path):
        agent = """\
  - id: alpha_id
    display_name: {name}
    description: Generic description for duplicated agent.
    color_hex: "#aabbcc"
    system_prompt: You are {name}.
"""
        body = "agents:\n" + agent.format(name="Alpha") + agent.format(name="Alpha2")
        path = _write_catalog(tmp_path, body)
        with pytest.raises(ValueError, match="alpha_id"):
            load_profiles_from_file(path)

    def test_missing_agents_key_raises_value_error(self, tmp_path: Path):
        path = _write_catalog(tmp_path, "version: 1\n")
        with pytest.raises(ValueError, match="agents"):
            load_profiles_from_file(path)

    def test_agents_file_env_var_is_used_when_resetting_registry(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setenv("AGENTS_FILE", str(_write_catalog(tmp_path, VALID_CATALOG)))
        reset_default_profiles()

        ids = {p.id for p in get_all_profiles()}
        assert {"sup_id", "alpha_id", "beta_id"} <= ids
        assert get_profile("Alpha").id == "alpha_id"
        assert get_profile("Boss").id == "sup_id"
        assert get_profile("Boss").is_supervisor is True

    def test_explicit_missing_agents_file_env_var_fails_loudly(
        self, tmp_path: Path, monkeypatch
    ):
        monkeypatch.setenv("AGENTS_FILE", str(tmp_path / "missing.yaml"))
        with pytest.raises(FileNotFoundError):
            reset_default_profiles()


class TestShippedCatalogIsConsistentWithShippedTopology:
    """Structural invariants only — no agent names are asserted here."""

    def test_every_agent_referenced_by_topology_exists(self):
        from src.domain.agents.debate_topology import load_topology

        top = load_topology()
        referenced = {
            top.supervisor,
            top.interpreter,
            top.reviewer,
            top.evaluator,
            *top.proposers,
            *top.implementers,
        }
        for name in referenced:
            get_profile(name)  # raises KeyError if the catalog is inconsistent

    def test_topology_validates_against_shipped_catalog(self):
        from src.domain.agents.debate_topology import load_topology

        top = load_topology()
        top.validate()

    def test_every_profile_has_meaningful_metadata(self):
        for profile in get_all_profiles():
            assert profile.id
            assert profile.display_name
            assert len(profile.description.strip()) > 10
            assert len(profile.system_prompt.strip()) > 50
            assert profile.color_hex.startswith("#") and len(profile.color_hex) == 7

    def test_ids_and_display_names_are_unique(self):
        profiles = get_all_profiles()
        assert len({p.id for p in profiles}) == len(profiles)
        assert len({p.display_name.lower() for p in profiles}) == len(profiles)

    def test_rag_agents_declare_a_filter_or_use_full_vault(self):
        for profile in get_all_profiles():
            if not profile.uses_rag:
                assert profile.rag_filter is None


class TestSupervisorEventsAndHitl:
    def test_hitl_response_supports_target_agents(self):
        resp = HITLResponse(decision=HITLDecision.APPROVE, target_agents=["a", "b"])
        assert resp.target_agents == ["a", "b"]

    def test_supervisor_event_accepts_display_name_string_role(self):
        event = SupervisorEvent(type=EventType.AGENT_STARTED, role="Any Name", content="")
        assert event.role == "Any Name"
