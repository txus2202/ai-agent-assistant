"""
Infrastructure Adapter: YAML Topology Provider

Resolves ``TOPOLOGY_FILE`` / ``./topology.yaml``, parses PyYAML outside the
domain layer, and validates against an ``IAgentCatalogRepository``.
"""
from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from src.domain.agents.debate_topology import DebateTopology
from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.domain.ports.agent_catalog_repository import IAgentCatalogRepository, ITopologyProvider
from src.infrastructure.config.yaml_agent_catalog import (
    YamlAgentCatalogRepository,
    project_root,
)


def resolve_topology_path(path: str | Path | None = None) -> Path:
    """Resolve the canonical topology YAML path via argument, TOPOLOGY_FILE env var, or root."""
    if path is not None:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Topology file not found: {path}")
        return p

    env_path = os.environ.get("TOPOLOGY_FILE")
    if env_path:
        p = Path(env_path)
        if not p.exists():
            raise FileNotFoundError(f"Topology file specified in TOPOLOGY_FILE not found: {p}")
        return p

    candidate = project_root() / "topology.yaml"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"Canonical topology configuration file not found: {candidate}"
    )


def _to_string_list(raw_value: Any) -> list[str]:
    if not raw_value:
        return []
    if isinstance(raw_value, (list, tuple)):
        return [str(x) for x in raw_value]
    return [str(raw_value)]


def load_topology(
    path: str | Path | None = None,
    *,
    agent_catalog: IAgentCatalogRepository | Sequence[SubAgentProfile] | None = None,
) -> DebateTopology:
    """
    Load and validate a DebateTopology from YAML.

    Validates against the provided ``agent_catalog`` (or loads the configured
    ``YamlAgentCatalogRepository`` if omitted).
    """
    target_path = resolve_topology_path(path)
    content = target_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content) or {}

    if "supervisor" not in data or data["supervisor"] is None:
        raise ValueError("Missing required topology slot in topology.yaml: 'supervisor'")

    top = DebateTopology(
        supervisor=str(data["supervisor"]),
        interpreters=tuple(_to_string_list(data.get("interpreters"))),
        proposers=tuple(_to_string_list(data.get("proposers"))),
        reviewers=tuple(_to_string_list(data.get("reviewers"))),
        evaluators=tuple(_to_string_list(data.get("evaluators"))),
        implementers=tuple(_to_string_list(data.get("implementers"))),
        project_name=str(data.get("project_name", "A.T.E.N.E.A.")),
        project_description=str(
            data.get(
                "project_description",
                "Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas",
            )
        ),
    )
    catalog_for_validation = agent_catalog if agent_catalog is not None else YamlAgentCatalogRepository()
    top.validate(catalog_for_validation)
    return top


class YamlTopologyProvider(ITopologyProvider):
    """YAML-backed topology provider cached per instance without module globals."""

    def __init__(
        self,
        agent_catalog: IAgentCatalogRepository,
        topology_path: str | Path | None = None,
    ) -> None:
        self._agent_catalog = agent_catalog
        self._topology_path = topology_path
        self._cached_topology: DebateTopology | None = None

    def get_topology(self) -> DebateTopology:
        if self._cached_topology is None:
            self._cached_topology = load_topology(
                self._topology_path,
                agent_catalog=self._agent_catalog,
            )
        return self._cached_topology

    def reload(self, topology_path: str | Path | None = None) -> DebateTopology:
        if topology_path is not None:
            self._topology_path = topology_path
        self._cached_topology = load_topology(
            self._topology_path,
            agent_catalog=self._agent_catalog,
        )
        return self._cached_topology

