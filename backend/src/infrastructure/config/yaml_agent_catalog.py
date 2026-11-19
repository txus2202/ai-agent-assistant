"""
Infrastructure Adapter: YAML & In-Memory Agent Catalog Repositories

Moves filesystem path resolution (PROJECT_ROOT, AGENTS_FILE), PyYAML parsing,
and catalog registry state out of ``domain/`` into ``infrastructure/``.
"""
from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import yaml

from src.domain.agents.sub_agent_profiles import (
    SubAgentProfile,
    index_profile_keys,
    normalize_profile_identifier,
)
from src.domain.ports.agent_catalog_repository import IAgentCatalogRepository
from src.domain.value_objects.document_chunk import SearchFilter

_REQUIRED_FIELDS = ("id", "display_name", "description", "color_hex", "system_prompt")
_RAG_FILTER_FIELDS = ("type", "phase", "layer", "status", "category", "domain")


def project_root() -> Path:
    """Absolute path to the repository root (independent of the working directory)."""
    override = os.environ.get("PROJECT_ROOT")
    if override:
        return Path(override)
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "agents.yaml").exists():
            return parent
    if len(p.parents) > 4:
        return p.parents[4]
    return p.parents[3] if len(p.parents) > 3 else p.parent


def default_agents_file() -> Path:
    """Catalog location: ``AGENTS_FILE`` env var, or ``<project_root>/agents.yaml``."""
    override = os.environ.get("AGENTS_FILE")
    return Path(override) if override else project_root() / "agents.yaml"


def _parse_rag_filter(raw: Any, agent_id: str) -> SearchFilter | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError(f"Agent '{agent_id}': 'rag_filter' must be a mapping")
    unknown = set(raw) - set(_RAG_FILTER_FIELDS)
    if unknown:
        raise ValueError(
            f"Agent '{agent_id}': unknown rag_filter field(s) {sorted(unknown)}; "
            f"allowed: {list(_RAG_FILTER_FIELDS)}"
        )
    return SearchFilter(**raw)


def _parse_profile(entry: Any, index: int) -> SubAgentProfile:
    if not isinstance(entry, dict):
        raise ValueError(f"agents[{index}] must be a mapping")
    label = entry.get("id", f"#{index}")
    for field_name in _REQUIRED_FIELDS:
        value = entry.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Agent '{label}': missing required field '{field_name}'")
    return SubAgentProfile(
        id=entry["id"].strip(),
        display_name=entry["display_name"].strip(),
        description=entry["description"].strip(),
        color_hex=entry["color_hex"].strip(),
        system_prompt=entry["system_prompt"].strip(),
        uses_rag=bool(entry.get("uses_rag", False)),
        rag_filter=_parse_rag_filter(entry.get("rag_filter"), str(label)),
        phonetic_aliases=tuple(str(a) for a in entry.get("phonetic_aliases") or ()),
        supports_hitl=bool(entry.get("supports_hitl", True)),
        is_supervisor=bool(entry.get("is_supervisor", False)),
        can_ingest_documents=bool(entry.get("can_ingest_documents", False)),
        tools=tuple(str(t) for t in entry.get("tools") or ()),
        default_provider=str(entry.get("default_provider") or entry.get("provider") or "").strip(),
        default_model=str(entry.get("default_model") or entry.get("model_name") or entry.get("model") or "").strip(),
    )


def load_profiles_from_file(path: str | Path) -> list[SubAgentProfile]:
    """
    Load and validate an agent catalog from a YAML file.

    Raises FileNotFoundError if missing and ValueError if malformed.
    """
    catalog_path = Path(path)
    if not catalog_path.exists():
        raise FileNotFoundError(f"Agent catalog file not found: {catalog_path}")

    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    entries = data.get("agents") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        raise ValueError(f"Agent catalog {catalog_path} must define an 'agents' list")

    profiles: list[SubAgentProfile] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        profile = _parse_profile(entry, index)
        if profile.id in seen:
            raise ValueError(f"Duplicate agent id '{profile.id}' in {catalog_path}")
        seen.add(profile.id)
        profiles.append(profile)

    if not any(p.is_supervisor for p in profiles):
        raise ValueError(
            f"Agent catalog {catalog_path} must define at least one supervisor agent (is_supervisor: true)"
        )

    return profiles


class InMemoryAgentCatalogRepository(IAgentCatalogRepository):
    """Scoped, dependency-free in-memory implementation of IAgentCatalogRepository."""

    def __init__(self, profiles: Sequence[SubAgentProfile] = ()) -> None:
        self._profiles: list[SubAgentProfile] = []
        self._registry_map: dict[str, SubAgentProfile] = {}
        for profile in profiles:
            self._profiles = [p for p in self._profiles if p.id != profile.id]
            self._profiles.append(profile)
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        self._registry_map.clear()
        for profile in self._profiles:
            for key in index_profile_keys(profile):
                self._registry_map[key] = profile

    def register_profile(self, profile: SubAgentProfile) -> None:
        self._profiles = [p for p in self._profiles if p.id != profile.id]
        self._profiles.append(profile)
        self._rebuild_index()

    def unregister_profile(self, identifier: str) -> bool:
        try:
            profile = self.get_profile(identifier)
        except KeyError:
            return False
        self._profiles = [p for p in self._profiles if p.id != profile.id]
        self._rebuild_index()
        return True

    def get_profile(self, identifier: str) -> SubAgentProfile:
        lookup = identifier if isinstance(identifier, str) else str(identifier)
        if lookup in self._registry_map:
            return self._registry_map[lookup]
        norm = normalize_profile_identifier(lookup)
        if norm in self._registry_map:
            return self._registry_map[norm]
        raise KeyError(f"No SubAgentProfile found for '{identifier}'")

    def get_all_profiles(self) -> list[SubAgentProfile]:
        return list(self._profiles)


class YamlAgentCatalogRepository(InMemoryAgentCatalogRepository):
    """YAML-backed agent catalog repository loaded on construction without globals."""

    def __init__(self, catalog_path: str | Path | None = None) -> None:
        self._catalog_path = Path(catalog_path) if catalog_path is not None else default_agents_file()
        loaded = load_profiles_from_file(self._catalog_path)
        super().__init__(profiles=loaded)

    @property
    def catalog_path(self) -> Path:
        return self._catalog_path

    def reload(self, catalog_path: str | Path | None = None) -> None:
        target = Path(catalog_path) if catalog_path is not None else default_agents_file()
        self._catalog_path = target
        self._profiles = list(load_profiles_from_file(target))
        self._rebuild_index()

