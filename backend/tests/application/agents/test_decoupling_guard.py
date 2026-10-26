"""
Architectural guard — the application/domain code must stay agnostic of the
concrete council.

No source file that implements generic behaviour may mention the name of any
agent shipped in the root ``agents.yaml`` (nor the built-in supervisor), nor
legacy agent-specific identifiers. If this test fails, a new coupling to the
current set of agents was introduced.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.agents.sub_agent_profiles import load_profiles_from_file

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent

GENERIC_SOURCES = [
    "src/application/agents/supervisor_agent.py",
    "src/application/agents/sub_agent_runner.py",
    "src/domain/agents/debate_topology.py",
    "src/domain/agents/supervisor_events.py",
    "src/presentation/api/ws/debate.py",
    "src/presentation/api/ws/wake_word.py",
    "src/presentation/api/routes/config.py",
    "src/presentation/api/config.py",
    "src/infrastructure/audio/local_audio_service.py",
    "src/infrastructure/audio/wake_word_service.py",
]

LEGACY_IDENTIFIERS = ["skip_hermes", "sphinx_critiques", "judge_history", "judge_content", "AgentRole"]


def _shipped_agent_names() -> list[str]:
    catalog = load_profiles_from_file(ROOT / "agents.yaml")
    return [p.display_name for p in catalog]


@pytest.mark.parametrize("relative_path", GENERIC_SOURCES)
def test_generic_sources_do_not_mention_concrete_agents(relative_path: str):
    source = (BACKEND / relative_path).read_text(encoding="utf-8")
    for name in _shipped_agent_names():
        assert name not in source, f"{relative_path} is coupled to agent '{name}'"
    for ident in LEGACY_IDENTIFIERS:
        assert ident not in source, f"{relative_path} contains legacy identifier '{ident}'"


def test_profiles_module_contains_no_concrete_agents_or_builtin_supervisor():
    source = (BACKEND / "src/domain/agents/sub_agent_profiles.py").read_text(encoding="utf-8")
    assert "BUILTIN_SUPERVISOR" not in source
    catalog_names = [p.display_name for p in load_profiles_from_file(ROOT / "agents.yaml")]
    for name in catalog_names:
        assert name not in source, f"sub_agent_profiles.py is coupled to agent '{name}'"
    for ident in ("_SENIOR_ARCHITECT", "_THE_JUDGE", "_DEVOPS_SECOPS", "_DIAGRAMMER", "AgentRole"):
        assert ident not in source


def test_supervisor_agent_prompts_are_domain_neutral():
    source = (BACKEND / "src/application/agents/supervisor_agent.py").read_text(encoding="utf-8")
    for domain_word in ("arquitect", "Redis"):
        assert domain_word.lower() not in source.lower(), f"domain word '{domain_word}' found"
