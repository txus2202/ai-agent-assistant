"""
Domain: SubAgentProfile Value Object & Pure Collection Helpers

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
  - tools: declarative tool/capability identifiers (e.g. ``image_viewer``, ``code_viewer``)

Pure domain module: contains zero YAML parsing, filesystem I/O, environment lookups,
or mutable global state. External catalogs are loaded through infrastructure adapters
implementing ``IAgentCatalogRepository``.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass

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
    default_provider: str = ""
    default_model: str = ""

    @property
    def supports_image_generation(self) -> bool:
        """Return True if this profile declares image design generation capability."""
        return "image_viewer" in self.tools

    @property
    def name(self) -> str:
        """The canonical name of the agent (matches display_name)."""
        return self.display_name


def normalize_profile_identifier(value: str) -> str:
    """Normalize an identifier or display name by stripping diacritics and casing."""
    normalized = unicodedata.normalize("NFD", value.lower().strip())
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def index_profile_keys(profile: SubAgentProfile) -> set[str]:
    """Return all canonical lookup keys (id, display_name, aliases, normalized forms)."""
    keys = {
        profile.id,
        profile.id.lower(),
        normalize_profile_identifier(profile.id),
        profile.display_name,
        profile.display_name.lower(),
        normalize_profile_identifier(profile.display_name),
    }
    for alias in profile.phonetic_aliases:
        keys.add(alias.lower())
        keys.add(normalize_profile_identifier(alias))
    return keys


def resolve_profile(identifier: str, profiles: Sequence[SubAgentProfile]) -> SubAgentProfile:
    """
    Resolve a ``SubAgentProfile`` from an explicit profile collection.

    Matches by unique ``id``, ``display_name``, normalized form, or phonetic alias.
    Raises ``KeyError`` if no matching profile exists.
    """
    lookup = identifier if isinstance(identifier, str) else str(identifier)
    norm_lookup = normalize_profile_identifier(lookup)
    lower_lookup = lookup.lower()

    for profile in profiles:
        keys = index_profile_keys(profile)
        if lookup in keys or lower_lookup in keys or norm_lookup in keys:
            return profile

    raise KeyError(f"No SubAgentProfile found for '{identifier}'")


def format_team_roster(
    profiles: Sequence[SubAgentProfile],
    exclude_id: str | None = None,
) -> str:
    """Format a truthful, markdown-structured roster of the council specialists.

    Lists all provided agents except the excluded one (e.g. the supervisor).
    """
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
