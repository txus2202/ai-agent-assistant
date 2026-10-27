"""
Unit tests for DebateTopology and the topology.yaml loader.

Layer: Domain (src.domain.agents.debate_topology)

The tests register their own generic agents, so they are independent of the
council shipped in the root ``agents.yaml`` / ``topology.yaml``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.agents.debate_topology import DebateTopology, load_topology
from src.domain.agents.sub_agent_profiles import (
    SubAgentProfile,
    register_profile,
    reset_default_profiles,
)


def _agent(agent_id: str, name: str, *, supervisor: bool = False) -> SubAgentProfile:
    return SubAgentProfile(
        id=agent_id,
        display_name=name,
        description=f"Generic test agent {name} for topology tests.",
        color_hex="#112233",
        system_prompt=f"You are {name}. " + "Generic instructions. " * 5,
        is_supervisor=supervisor,
    )


@pytest.fixture(autouse=True)
def generic_agents():
    reset_default_profiles()
    register_profile(_agent("boss", "Boss", supervisor=True))
    for agent_id, name in (
        ("reader", "Reader"),
        ("maker_a", "MakerA"),
        ("maker_b", "MakerB"),
        ("checker", "Checker"),
        ("doer_a", "DoerA"),
        ("doer_b", "DoerB"),
    ):
        register_profile(_agent(agent_id, name))
    yield
    reset_default_profiles()


def _topology(**overrides) -> DebateTopology:
    values = {
        "supervisor": "Boss",
        "interpreters": ("Reader",),
        "proposers": ("MakerA", "MakerB"),
        "reviewers": ("Checker",),
        "evaluators": ("Checker",),
        "implementers": ("DoerA", "DoerB"),
    }
    values.update(overrides)
    return DebateTopology(**values)


def test_valid_topology_instantiation_and_validation():
    top = _topology()
    assert top.supervisor == "Boss"
    assert top.interpreters == ("Reader",)
    assert top.proposers == ("MakerA", "MakerB")
    assert top.reviewers == ("Checker",)
    assert top.evaluators == ("Checker",)
    assert top.implementers == ("DoerA", "DoerB")
    top.validate()


def test_topology_allows_empty_optional_roles():
    top = DebateTopology(
        supervisor="Boss",
        interpreters=(),
        proposers=(),
        reviewers=(),
        evaluators=(),
        implementers=(),
    )
    top.validate()
    assert top.interpreters == ()
    assert top.proposers == ()
    assert top.reviewers == ()
    assert top.evaluators == ()
    assert top.implementers == ()


def test_topology_is_frozen_immutable():
    top = _topology()
    with pytest.raises((AttributeError, TypeError)):
        top.supervisor = "Other"  # type: ignore[misc]


def test_validation_fails_if_supervisor_is_not_marked_is_supervisor():
    top = _topology(supervisor="Reader")
    with pytest.raises(ValueError, match="not a valid supervisor"):
        top.validate()


def test_validation_fails_if_agent_does_not_exist():
    top = _topology(interpreters=("NonExistentAgent999",))
    with pytest.raises(KeyError):
        top.validate()


def test_validation_accepts_agents_added_at_runtime():
    register_profile(_agent("maker_c", "MakerC"))
    _topology(proposers=("MakerA", "MakerB", "MakerC")).validate()


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "topology.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def test_load_topology_from_valid_yaml(tmp_path: Path):
    path = _write(
        tmp_path,
        """\
version: "2.0"
supervisor: "Boss"
interpreters:
  - "Reader"
proposers:
  - "MakerB"
  - "MakerA"
reviewers:
  - "Checker"
evaluators:
  - "Checker"
implementers:
  - "DoerA"
""",
    )
    top = load_topology(path)
    assert top.supervisor == "Boss"
    assert top.interpreters == ("Reader",)
    assert top.proposers == ("MakerB", "MakerA")
    assert top.reviewers == ("Checker",)
    assert top.evaluators == ("Checker",)
    assert top.implementers == ("DoerA",)


def test_load_topology_with_empty_or_missing_roles(tmp_path: Path):
    path = _write(
        tmp_path,
        """\
supervisor: "Boss"
interpreters: []
proposers:
  - "MakerA"
""",
    )
    top = load_topology(path)
    assert top.supervisor == "Boss"
    assert top.interpreters == ()
    assert top.proposers == ("MakerA",)
    assert top.reviewers == ()
    assert top.evaluators == ()
    assert top.implementers == ()


def test_load_topology_missing_supervisor_raises_value_error(tmp_path: Path):
    path = _write(
        tmp_path,
        """\
interpreters: ["Reader"]
proposers: ["MakerA"]
""",
    )
    with pytest.raises(ValueError, match="supervisor"):
        load_topology(path)


def test_load_topology_explicit_missing_file_raises_not_found():
    with pytest.raises(FileNotFoundError):
        load_topology(Path("/non/existent/path/topology_never.yaml"))


def test_load_topology_uses_topology_file_env_var(tmp_path: Path, monkeypatch):
    path = _write(
        tmp_path,
        """\
supervisor: "Boss"
proposers: ["MakerA"]
""",
    )
    monkeypatch.setenv("TOPOLOGY_FILE", str(path))
    top = load_topology()
    assert top.supervisor == "Boss"
    assert top.proposers == ("MakerA",)


def test_shipped_topology_is_valid_against_shipped_catalog():
    """Structural check of the real ./topology.yaml."""
    reset_default_profiles()
    top = load_topology()
    top.validate()
    assert top.supervisor == "Atenea"
    assert "Hermes" in top.interpreters
    assert "Ícaro" in top.proposers
    assert "Hestia" in top.proposers
    assert "Sphinx" in top.reviewers
    assert "Sphinx" in top.evaluators
    assert "Aracne" in top.implementers
    assert "Hefesto" in top.implementers

