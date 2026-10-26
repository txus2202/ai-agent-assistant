"""
Shared fixtures for application-layer agent tests.

Points the agent catalog and debate topology to a *generic* council
(``tests/fixtures/council``) so that these tests never depend on the concrete
agents (names, number, domain) shipped in the root ``agents.yaml`` /
``topology.yaml``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.domain.agents.sub_agent_profiles import reset_default_profiles

COUNCIL_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "council"


@pytest.fixture(autouse=True)
def generic_council(monkeypatch):
    monkeypatch.setenv("AGENTS_FILE", str(COUNCIL_DIR / "agents.yaml"))
    monkeypatch.setenv("TOPOLOGY_FILE", str(COUNCIL_DIR / "topology.yaml"))
    reset_default_profiles()
    yield
    monkeypatch.undo()
    reset_default_profiles()
