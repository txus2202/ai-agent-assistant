"""
Presentation WS Helpers: Learning Command & Attachment Parser

Pure parsing helpers for Spanish learning directives, tags, target domains,
pending_learning payloads, source types, and safe attachment validation.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from src.domain.ports.source_extractor import SourceType

logger = logging.getLogger(__name__)

LEARN_DIRECTIVE_REGEX = re.compile(
    r"^(?:/learn|aprende\s+esto|aprende|memoriza|guarda\s+este\s+conocimiento)[:\s]+(.+)",
    re.IGNORECASE | re.DOTALL,
)

BRACKET_TAGS_REGEX = re.compile(
    r"\[(?:tag|etiqueta)s?:\s*([^\s\]][^\]\r\n]*)\]",
    re.IGNORECASE,
)

NL_TAGS_REGEX = re.compile(
    r"\b(?:con\s+(?:(?:los|las)\s+)?)?(?:tag|etiqueta)s?:\s*([^\s#\[\]][^#\r\n\[\]]*)",
    re.IGNORECASE,
)

HASHTAGS_REGEX = re.compile(
    r"(?<!\S)#([a-zA-Z0-9_\-\.]+)",
)

_DOMAIN_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("01_enterprise_architecture", ("enterprise", "empresa", "corporativ", "estándar", "estandar", "01_enterprise")),
    ("00_meta_project", ("tfm", "plataforma", "meta_project", "00_meta")),
    ("deliberations/sessions", ("deliberation", "deliberación", "acta", "sesion", "sesión")),
    ("learned", ("investigacion", "investigación", "learned", "externo", "whitepaper")),
)

_SKIP_TAGS_EXACT = frozenset({
    "sin tags", "sin tag", "sin etiquetas", "sin etiqueta",
    "no", "ninguno", "ninguna", "asímilalo directamente", "asimilalo directamente",
    "directamente", "adelante", "omitir", "ningun tag", "ninguna etiqueta", "no gracias",
})
_SKIP_TAGS_PREFIXES = ("sin tag", "sin etiqueta", "asimil", "adelante")


_HTTP_SCHEMES: tuple[str, str] = ("http://", "https://")


def is_http_url(source: str) -> bool:
    return isinstance(source, str) and source.strip().lower().startswith(_HTTP_SCHEMES)


def detect_source_type(source: str) -> SourceType:
    lower = source.lower()
    if lower.startswith(_HTTP_SCHEMES):
        return SourceType.URL
    if lower.endswith(".pdf"):
        return SourceType.PDF
    if lower.endswith((".md", ".markdown")):
        return SourceType.MARKDOWN
    if lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return SourceType.IMAGE
    return SourceType.PDF


def _append_unique_tags(target: list[str], candidates: Iterable[str]) -> None:
    for item in candidates:
        clean = item.strip().lstrip("#")
        if clean and clean not in target and not clean.startswith(_HTTP_SCHEMES):
            target.append(clean)


def extract_tags(text: str) -> list[str]:
    tags: list[str] = []
    bracket_match = BRACKET_TAGS_REGEX.search(text)
    if bracket_match:
        _append_unique_tags(tags, bracket_match.group(1).split(","))
    nl_match = NL_TAGS_REGEX.search(text)
    if nl_match:
        _append_unique_tags(tags, nl_match.group(1).split(","))
    _append_unique_tags(tags, HASHTAGS_REGEX.findall(text))
    return tags


def extract_domain(text: str) -> str | None:
    low = text.lower()
    for domain_id, keywords in _DOMAIN_KEYWORDS:
        if any(keyword in low for keyword in keywords):
            return domain_id
    return None


def is_skip_tags_response(text: str) -> bool:
    low = text.strip().lower()
    return low in _SKIP_TAGS_EXACT or low.startswith(_SKIP_TAGS_PREFIXES)


def resolve_pending_tags(user_request: str) -> list[str]:
    """Parse user reply to the pending_learning prompt into tag names."""
    if is_skip_tags_response(user_request):
        return []
    tags = extract_tags(user_request)
    if not tags and not extract_domain(user_request):
        tags = [
            t.strip().lstrip("#")
            for t in re.split(r"[,;]", user_request)
            if t.strip() and len(t.strip()) < 30
        ]
    return tags


def parse_pending_learning_payload(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            logger.debug("Ignoring malformed pending_learning JSON payload")
            return None
    return None


def extract_pending_from_event(ev: dict[str, Any]) -> dict[str, Any] | None:
    if ev.get("type") not in ("agent_completed", "done"):
        return None
    meta = ev.get("metadata")
    if not isinstance(meta, dict):
        return None
    return parse_pending_learning_payload(meta.get("pending_learning"))


def find_pending_learning_in_events(events: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    for ev in reversed(list(events)):
        pending = extract_pending_from_event(ev)
        if pending:
            return pending
        if ev.get("type") != "user_message":
            break
    return None


def validate_attachments(
    raw_attachments: Any,
    user_id: str | None,
    path_resolver: Callable[[str, str | None], Path],
) -> list[str]:
    if raw_attachments is None:
        return []
    if not isinstance(raw_attachments, list):
        raise ValueError("attachments must be a list")

    validated: list[str] = []
    for item in raw_attachments:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Each attachment must be a non-empty string")
        cleaned = item.strip()
        if is_http_url(cleaned):
            validated.append(cleaned)
        else:
            validated.append(str(path_resolver(cleaned, user_id)))
    return validated

