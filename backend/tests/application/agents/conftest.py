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

from src.domain.agents.debate_topology import DebateTopology
from src.infrastructure.config.yaml_agent_catalog import YamlAgentCatalogRepository
from src.infrastructure.config.yaml_topology_provider import (
    YamlTopologyProvider,
    load_topology,
)

COUNCIL_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "council"


@pytest.fixture(autouse=True)
def generic_council_env(monkeypatch):
    monkeypatch.setenv("AGENTS_FILE", str(COUNCIL_DIR / "agents.yaml"))
    monkeypatch.setenv("TOPOLOGY_FILE", str(COUNCIL_DIR / "topology.yaml"))


@pytest.fixture
def generic_catalog(generic_council_env) -> YamlAgentCatalogRepository:
    return YamlAgentCatalogRepository(COUNCIL_DIR / "agents.yaml")


@pytest.fixture
def generic_topology_provider(generic_catalog: YamlAgentCatalogRepository) -> YamlTopologyProvider:
    return YamlTopologyProvider(
        agent_catalog=generic_catalog,
        topology_path=COUNCIL_DIR / "topology.yaml",
    )


@pytest.fixture
def generic_topology(generic_catalog: YamlAgentCatalogRepository) -> DebateTopology:
    return load_topology(COUNCIL_DIR / "topology.yaml", agent_catalog=generic_catalog)
