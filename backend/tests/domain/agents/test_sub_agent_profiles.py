"""
RED Tests — AgentRole & SubAgentProfile (Feature: feature_sub_agents.md)

Layer: Domain

Scenarios:
  4. AgentRole enum has exactly 6 roles
  5. SubAgentProfile is frozen (immutable)
  6. Diagrammer system_prompt contains mermaid instruction
  + profile registry completeness
"""
from __future__ import annotations

import pytest


class TestAgentRole:
    def test_has_seven_roles(self):
        from src.domain.agents.agent_role import AgentRole

        assert len(list(AgentRole)) == 7

    def test_expected_roles_exist(self):
        from src.domain.agents.agent_role import AgentRole

        expected = {
            "NL_INTERPRETER",
            "INNOVATOR",
            "SENIOR_ARCHITECT",
            "THE_JUDGE",
            "DEVOPS_SECOPS",
            "DIAGRAMMER",
            "LEARNING",
        }
        actual = {role.name for role in AgentRole}
        assert actual == expected

    def test_role_values_are_strings(self):
        from src.domain.agents.agent_role import AgentRole

        for role in AgentRole:
            assert isinstance(role.value, str)


class TestSubAgentProfiles:
    def test_all_roles_have_a_profile(self):
        from src.domain.agents.agent_role import AgentRole
        from src.domain.agents.sub_agent_profiles import get_profile

        for role in AgentRole:
            profile = get_profile(role)
            assert profile is not None
            assert profile.role == role

    def test_profile_is_frozen_immutable(self):
        from src.domain.agents.agent_role import AgentRole
        from src.domain.agents.sub_agent_profiles import get_profile

        profile = get_profile(AgentRole.NL_INTERPRETER)
        with pytest.raises((AttributeError, TypeError)):
            profile.system_prompt = "mutated"  # type: ignore[misc]

    def test_profile_has_display_name(self):
        from src.domain.agents.agent_role import AgentRole
        from src.domain.agents.sub_agent_profiles import get_profile

        for role in AgentRole:
            profile = get_profile(role)
            assert profile.display_name is not None
            assert len(profile.display_name) > 0

    def test_nl_interpreter_does_not_use_rag(self):
        from src.domain.agents.agent_role import AgentRole
        from src.domain.agents.sub_agent_profiles import get_profile

        profile = get_profile(AgentRole.NL_INTERPRETER)
        assert profile.uses_rag is False

    def test_senior_architect_uses_rag_with_status_filter(self):
        from src.domain.agents.agent_role import AgentRole
        from src.domain.agents.sub_agent_profiles import get_profile

        profile = get_profile(AgentRole.SENIOR_ARCHITECT)
        assert profile.uses_rag is True
        assert profile.rag_filter is not None
        assert profile.rag_filter.status == "implemented"

    def test_innovator_uses_rag_with_type_spec_filter(self):
        from src.domain.agents.agent_role import AgentRole
        from src.domain.agents.sub_agent_profiles import get_profile

        profile = get_profile(AgentRole.INNOVATOR)
        assert profile.uses_rag is True
        assert profile.rag_filter is not None
        assert profile.rag_filter.type == "spec"

    def test_the_judge_uses_rag_with_type_adr_filter(self):
        from src.domain.agents.agent_role import AgentRole
        from src.domain.agents.sub_agent_profiles import get_profile

        profile = get_profile(AgentRole.THE_JUDGE)
        assert profile.uses_rag is True
        assert profile.rag_filter is not None
        assert profile.rag_filter.type == "adr"

    def test_diagrammer_system_prompt_mentions_mermaid(self):
        from src.domain.agents.agent_role import AgentRole
        from src.domain.agents.sub_agent_profiles import get_profile

        profile = get_profile(AgentRole.DIAGRAMMER)
        assert "mermaid" in profile.system_prompt.lower()

    def test_all_profiles_have_non_empty_system_prompt(self):
        from src.domain.agents.agent_role import AgentRole
        from src.domain.agents.sub_agent_profiles import get_profile

        for role in AgentRole:
            profile = get_profile(role)
            assert len(profile.system_prompt.strip()) > 50  # meaningful, not empty
