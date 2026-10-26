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
        "interpreter": "Reader",
        "proposers": ("MakerA", "MakerB"),
        "reviewer": "Checker",
        "evaluator": "Checker",
        "implementers": ("DoerA", "DoerB"),
        "review_rounds": 1,
    }
    values.update(overrides)
    return DebateTopology(**values)


def test_valid_topology_instantiation_and_validation():
    top = _topology()
    assert top.supervisor == "Boss"
    assert top.proposers == ("MakerA", "MakerB")
    assert top.implementers == ("DoerA", "DoerB")
    assert top.review_rounds == 1
    top.validate()


def test_topology_has_no_default_agents():
    with pytest.raises(TypeError):
        DebateTopology()  # type: ignore[call-arg]


def test_topology_is_frozen_immutable():
    top = _topology()
    with pytest.raises((AttributeError, TypeError)):
        top.supervisor = "Other"  # type: ignore[misc]


def test_validation_fails_if_supervisor_is_not_marked_is_supervisor():
    with pytest.raises(ValueError, match="not a valid supervisor"):
        _topology(supervisor="Reader").validate()


def test_validation_fails_if_agent_does_not_exist():
    with pytest.raises(KeyError):
        _topology(interpreter="NonExistentAgent999").validate()


def test_validation_fails_if_no_proposers():
    with pytest.raises(ValueError, match="At least one proposer"):
        _topology(proposers=()).validate()


def test_validation_fails_if_negative_review_rounds():
    with pytest.raises(ValueError, match="review_rounds"):
        _topology(review_rounds=-1).validate()


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
version: "1.0"
supervisor: "Boss"
interpreter: "Reader"
proposers:
  - "MakerB"
  - "MakerA"
reviewer: "Checker"
evaluator: "Checker"
implementers:
  - "DoerA"
review_rounds: 3
""",
    )
    top = load_topology(path)
    assert top.supervisor == "Boss"
    assert top.interpreter == "Reader"
    assert top.proposers == ("MakerB", "MakerA")
    assert top.reviewer == "Checker"
    assert top.evaluator == "Checker"
    assert top.implementers == ("DoerA",)
    assert top.review_rounds == 3


def test_load_topology_missing_slot_raises_value_error(tmp_path: Path):
    path = _write(
        tmp_path,
        """\
supervisor: "Boss"
interpreter: "Reader"
proposers: ["MakerA"]
evaluator: "Checker"
implementers: ["DoerA"]
""",
    )
    with pytest.raises(ValueError, match="Missing required topology slot"):
        load_topology(path)


def test_load_topology_explicit_missing_file_raises_not_found():
    with pytest.raises(FileNotFoundError):
        load_topology(Path("/non/existent/path/topology_never.yaml"))


def test_load_topology_uses_topology_file_env_var(tmp_path: Path, monkeypatch):
    path = _write(
        tmp_path,
        """\
supervisor: "Boss"
interpreter: "Reader"
proposers: ["MakerA"]
reviewer: "Checker"
evaluator: "Checker"
implementers: ["DoerA"]
""",
    )
    monkeypatch.setenv("TOPOLOGY_FILE", str(path))
    top = load_topology()
    assert top.proposers == ("MakerA",)


def test_shipped_topology_is_valid_against_shipped_catalog():
    """Structural check of the real ./topology.yaml (no agent names asserted)."""
    reset_default_profiles()
    top = load_topology()
    top.validate()
    assert len(top.proposers) >= 1
