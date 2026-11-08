"""
Domain: SubAgentProfile & Dynamic Agent Registry

Value object describing an agent's configuration:
  - id: unique string identifier / slug (also the key used to persist per-agent LLM config)
  - display_name: human-readable name shown in the UI / logs / topology
  - description: short summary of the agent's responsibility
  - color_hex: UI theme accent color
  - system_prompt: the agent's expertise and instructions, injected before every prompt
  - uses_rag: whether this agent queries the knowledge vault before answering
  - rag_filter: optional metadata filter for vector search (None = full vault)
  - phonetic_aliases: tuple of voice/phonetic trigger keywords for STT/wake words
  - supports_hitl: whether this agent participates in Human-in-the-Loop checkpoints
  - is_supervisor: whether this agent is a strategic supervisor / orchestrator
  - can_ingest_documents: whether this agent ingests documents into the knowledge vault

The council is NOT defined in code. All agent profiles (including the
supervisor) are declared in the external catalog ``agents.yaml`` (project
root, overridable through the ``AGENTS_FILE`` environment variable) and can also
be added or removed at runtime with ``register_profile`` / ``unregister_profile``.
"""
from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.domain.value_objects.document_chunk import SearchFilter


@dataclass(frozen=True)
class SubAgentProfile:
    """Immutable configuration for an agent of the council."""

    id: str
    display_name: str
    description: str
    color_hex: str
    system_prompt: str
    uses_rag: bool = False
    rag_filter: SearchFilter | None = None
    phonetic_aliases: tuple[str, ...] = ()
    supports_hitl: bool = True
    is_supervisor: bool = False
    can_ingest_documents: bool = False
    tools: tuple[str, ...] = ()

    @property
    def supports_image_generation(self) -> bool:
        """Return True if this profile supports visual/image design generation."""
        return "image_viewer" in self.tools or self.id in ("fidias", "fídias")

    @property
    def name(self) -> str:
        """The canonical name of the agent (matches display_name)."""
        return self.display_name




# ---------------------------------------------------------------------------
# External catalog (agents.yaml)
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = ("id", "display_name", "description", "color_hex", "system_prompt")
_RAG_FILTER_FIELDS = ("type", "phase", "layer", "status")


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
    )


def load_profiles_from_file(path: str | Path) -> list[SubAgentProfile]:
    """
    Load and validate the agent catalog from a YAML file.

    Raises FileNotFoundError if the file does not exist and ValueError if the
    catalog is malformed (no 'agents' list, missing required field, duplicate id).
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


# ---------------------------------------------------------------------------
# Dynamic Agent Registry
# ---------------------------------------------------------------------------

_REGISTRY_MAP: dict[str, SubAgentProfile] = {}
_ALL_PROFILES: list[SubAgentProfile] = []


def _normalize_name(s: str) -> str:
    n = unicodedata.normalize("NFD", s.lower().strip())
    return "".join(c for c in n if unicodedata.category(c) != "Mn")


def _index_keys(profile: SubAgentProfile) -> set[str]:
    keys = {
        profile.id,
        profile.id.lower(),
        _normalize_name(profile.id),
        profile.display_name,
        profile.display_name.lower(),
        _normalize_name(profile.display_name),
    }
    for alias in profile.phonetic_aliases:
        keys.add(alias.lower())
        keys.add(_normalize_name(alias))
    return keys


def _rebuild_index() -> None:
    _REGISTRY_MAP.clear()
    for profile in _ALL_PROFILES:
        for key in _index_keys(profile):
            _REGISTRY_MAP[key] = profile


def register_profile(profile: SubAgentProfile) -> None:
    """
    Register (or replace, matching by id) a SubAgentProfile in the dynamic registry.
    Indexes the profile by id, display_name, normalized versions and phonetic aliases.
    """
    _ALL_PROFILES[:] = [p for p in _ALL_PROFILES if p.id != profile.id]
    _ALL_PROFILES.append(profile)
    _rebuild_index()


def unregister_profile(identifier: str) -> bool:
    """Unregister a profile by id, display_name or alias. Returns False if unknown."""
    try:
        profile = get_profile(identifier)
    except KeyError:
        return False
    _ALL_PROFILES[:] = [p for p in _ALL_PROFILES if p.id != profile.id]
    _rebuild_index()
    return True


def get_profile(identifier: str) -> SubAgentProfile:
    """
    Return the SubAgentProfile for ``identifier``.
    Resolves by unique id, display_name, normalized name, or phonetic alias.
    Raises KeyError if not found.
    """
    if not isinstance(identifier, str):
        identifier = str(identifier)

    if identifier in _REGISTRY_MAP:
        return _REGISTRY_MAP[identifier]
    norm = _normalize_name(identifier)
    if norm in _REGISTRY_MAP:
        return _REGISTRY_MAP[norm]

    raise KeyError(f"No SubAgentProfile found for '{identifier}'")


def get_all_profiles() -> list[SubAgentProfile]:
    """Return all registered SubAgentProfile instances in registration order."""
    return list(_ALL_PROFILES)


def format_team_roster(exclude_id: str | None = None) -> str:
    """Format a truthful, markdown-structured roster of the council specialists.

    Lists all registered agents except the excluded one (e.g. the supervisor).
    """
    profiles = get_all_profiles()
    team_members = [p for p in profiles if p.id != exclude_id]
    if not team_members:
        return ""
    lines = [
        "# MIEMBROS OFICIALES DEL CONSEJO TÉCNICO",
        "A continuación figura la lista veraz y oficial de los especialistas que componen el consejo técnico. "
        "Si debes presentarte o presentar al equipo y a sus miembros, o explicar qué hace cada uno, "
        "básate ESTRICTAMENTE en esta información oficial y no inventes ningún otro agente ni función:",
    ]
    for p in team_members:
        lines.append(f"- **{p.display_name}**: {p.description}")
    return "\n".join(lines)


def reset_default_profiles() -> None:
    """
    Reset the registry to its configured state: all agents loaded from
    the external catalog (``AGENTS_FILE`` or ``./agents.yaml``).
    """
    _ALL_PROFILES.clear()
    for profile in load_profiles_from_file(default_agents_file()):
        _ALL_PROFILES[:] = [p for p in _ALL_PROFILES if p.id != profile.id]
        _ALL_PROFILES.append(profile)
    _rebuild_index()


# Initialize registry on import
reset_default_profiles()
