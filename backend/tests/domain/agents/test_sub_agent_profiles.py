"""
Pure Domain Tests — SubAgentProfile, Collection Resolution & Team Roster Formatting.

Layer: Domain (zero YAML parsing, zero filesystem I/O, zero mutable globals).
"""
from __future__ import annotations

import pytest

from src.domain.agents.sub_agent_profiles import (
    SubAgentProfile,
    format_team_roster,
    index_profile_keys,
    normalize_profile_identifier,
    resolve_profile,
)
from src.domain.agents.supervisor_events import (
    EventType,
    HITLDecision,
    HITLResponse,
    SupervisorEvent,
)
from src.domain.value_objects.document_chunk import SearchFilter


def _profile(agent_id: str, name: str, **kwargs) -> SubAgentProfile:
    return SubAgentProfile(
        id=agent_id,
        display_name=name,
        description=f"Generic test agent {name} used for domain tests.",
        color_hex="#112233",
        system_prompt=f"You are {name}. " + "Generic instructions. " * 5,
        **kwargs,
    )


class TestSubAgentProfileModel:
    def test_sub_agent_profiles_module_has_no_builtin_constants_or_mutable_globals(self):
        import src.domain.agents.sub_agent_profiles as mod

        assert not hasattr(mod, "BUILTIN_SUPERVISOR")
        assert not hasattr(mod, "_REGISTRY_MAP")
        assert not hasattr(mod, "_ALL_PROFILES")

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
        assert profile.tools == ()
        assert profile.supports_image_generation is False

    def test_name_property_matches_display_name(self):
        assert _profile("alpha_id", "Alpha").name == "Alpha"

    def test_supports_image_generation_is_strictly_declarative_on_tools(self):
        with_tool = _profile("any_designer", "Designer", tools=("code_viewer", "image_viewer"))
        without_tool_fidias = _profile("fidias", "Fídias", tools=("code_viewer",))

        assert with_tool.supports_image_generation is True
        assert without_tool_fidias.supports_image_generation is False

    def test_rag_filter_attachment(self):
        profile = _profile(
            "rag_id",
            "RagAgent",
            uses_rag=True,
            rag_filter=SearchFilter(category=("enterprise", "external-learning")),
        )
        assert profile.rag_filter is not None
        assert profile.rag_filter.category == ("enterprise", "external-learning")


class TestPureCollectionLookupAndFormatting:
    def test_resolve_profile_by_id_name_normalized_and_alias(self):
        profiles = [
            _profile("sup_id", "Boss", is_supervisor=True),
            _profile("alpha_id", "Álpha", phonetic_aliases=("alfa", "al fa")),
        ]

        assert resolve_profile("sup_id", profiles).display_name == "Boss"
        assert resolve_profile("alpha_id", profiles).display_name == "Álpha"
        assert resolve_profile("Álpha", profiles).id == "alpha_id"
        assert resolve_profile("alpha", profiles).id == "alpha_id"
        assert resolve_profile("ALFA", profiles).id == "alpha_id"
        assert normalize_profile_identifier("  ÁÉÍ  ") == "aei"
        assert "alfa" in index_profile_keys(profiles[1])

    def test_unknown_identifier_raises_key_error(self):
        profiles = [_profile("sup_id", "Boss", is_supervisor=True)]
        with pytest.raises(KeyError):
            resolve_profile("non_existent_agent", profiles)

    def test_format_team_roster_lists_specialists_excluding_supervisor(self):
        sup = _profile("sup_id", "Boss", is_supervisor=True)
        alpha = _profile("alpha_id", "Alpha")
        beta = _profile("beta_id", "Beta")

        roster = format_team_roster([sup, alpha, beta], exclude_id=sup.id)
        assert "MIEMBROS OFICIALES DEL CONSEJO TÉCNICO" in roster
        assert "**Alpha**: Generic test agent Alpha" in roster
        assert "**Beta**: Generic test agent Beta" in roster
        assert "**Boss**:" not in roster

    def test_format_team_roster_returns_empty_when_no_specialists(self):
        sup = _profile("sup_id", "Boss", is_supervisor=True)
        assert format_team_roster([sup], exclude_id=sup.id) == ""


class TestSupervisorEventsAndHitl:
    def test_hitl_response_supports_target_agents(self):
        resp = HITLResponse(decision=HITLDecision.APPROVE, target_agents=["a", "b"])
        assert resp.target_agents == ["a", "b"]

    def test_supervisor_event_accepts_display_name_string_role(self):
        event = SupervisorEvent(type=EventType.AGENT_STARTED, role="Any Name", content="")
        assert event.role == "Any Name"
