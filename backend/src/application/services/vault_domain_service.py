"""
Application Service: VaultDomainService

Discovers, inspects, and creates hierarchical knowledge domains within the Obsidian vault.
Encapsulates MOC (Map of Content) management and directory hygiene.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(frozen=True)
class KnowledgeDomain:
    """Represents a segregated domain of knowledge inside the vault."""

    id: str
    name: str
    description: str
    path: str
    moc_file: str
    document_count: int = 0
    is_system: bool = False


# Known core domains with display names and descriptions
CORE_DOMAINS: dict[str, dict[str, str]] = {
    "00_meta_project": {
        "name": "Plataforma & TFM",
        "description": "Especificaciones y arquitectura de ai-agent-assistant y ATENEA",
    },
    "01_enterprise_architecture": {
        "name": "Arquitectura Empresarial",
        "description": "Estándares técnicos, seguridad y catálogo de tecnologías corporativas",
    },
    "learned": {
        "name": "Investigación Externa",
        "description": "Conocimiento adquirido de fuentes externas (PDF/URL) asimilado por Metis",
    },
    "deliberations": {
        "name": "Actas y Deliberaciones",
        "description": "Acuerdos y actas generadas por Calíope tras debates del consejo",
    },
}

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]+$")


class VaultDomainService:
    """Stateless service to manage vault knowledge domains."""

    @classmethod
    def _resolve_moc_rel(cls, dir_path: Path, vault_root: Path, fallback_id: str) -> str:
        candidates = list(dir_path.glob("MOC_*.md"))
        if candidates:
            return candidates[0].relative_to(vault_root).as_posix()
        return f"{fallback_id}/MOC_{fallback_id}.md"

    @classmethod
    def _list_system_domains(cls, vault_root: Path) -> list[KnowledgeDomain]:
        domains: list[KnowledgeDomain] = []
        for domain_id, info in CORE_DOMAINS.items():
            dir_path = vault_root / domain_id
            if not dir_path.is_dir():
                continue

            doc_count = len(list(dir_path.rglob("*.md")))
            moc_rel = cls._resolve_moc_rel(dir_path, vault_root, domain_id)
            domains.append(
                KnowledgeDomain(
                    id=domain_id,
                    name=info["name"],
                    description=info["description"],
                    path=domain_id,
                    moc_file=moc_rel,
                    document_count=doc_count,
                    is_system=True,
                )
            )
        return domains

    @classmethod
    def _discover_custom_domains(cls, vault_root: Path) -> list[KnowledgeDomain]:
        domains: list[KnowledgeDomain] = []
        for item in sorted(vault_root.iterdir()):
            if not item.is_dir() or item.name.startswith(".") or item.name in CORE_DOMAINS:
                continue

            doc_count = len(list(item.rglob("*.md")))
            moc_rel = cls._resolve_moc_rel(item, vault_root, item.name)
            clean_name = item.name.replace("_", " ").title()
            domains.append(
                KnowledgeDomain(
                    id=item.name,
                    name=clean_name,
                    description=f"Dominio personalizado: {clean_name}",
                    path=item.name,
                    moc_file=moc_rel,
                    document_count=doc_count,
                    is_system=False,
                )
            )
        return domains

    @classmethod
    def list_domains(cls, vault_root: Path) -> list[KnowledgeDomain]:
        """Scan vault_root and return all configured and discovered knowledge domains."""
        if not vault_root.exists() or not vault_root.is_dir():
            return []

        resolved_root = vault_root.resolve()
        return cls._list_system_domains(resolved_root) + cls._discover_custom_domains(resolved_root)

    @staticmethod
    def _resolve_safe_domain_paths(vault_root: Path, domain_id: str) -> tuple[str, str, Path, Path, Path]:
        raw_id = domain_id.strip()
        clean_id = os.path.basename(raw_id)
        if not clean_id or clean_id != raw_id or not _SAFE_ID_RE.fullmatch(clean_id):
            raise ValueError(f"Invalid domain ID '{domain_id}'. Must contain only alphanumeric, '_' or '-'.")

        vault_real = os.path.realpath(str(vault_root))
        vault_prefix = vault_real + os.sep
        domain_real = os.path.realpath(os.path.join(vault_real, clean_id))
        if not domain_real.startswith(vault_prefix):
            raise ValueError(f"Invalid domain ID '{domain_id}': path traversal detected.")

        clean_slug = clean_id.replace("-", "_")
        moc_filename = f"MOC_{clean_slug}.md"
        moc_real = os.path.realpath(os.path.join(domain_real, moc_filename))
        if not moc_real.startswith(domain_real + os.sep) or not moc_real.startswith(vault_prefix):
            raise ValueError(f"Invalid MOC filename '{moc_filename}'.")

        return clean_id, vault_prefix, Path(vault_real), Path(domain_real), Path(moc_real)

    @staticmethod
    def _ensure_moc_file(moc_path: Path, clean_id: str, name: str, description: str) -> None:
        if moc_path.exists():
            return
        today_str = datetime.now().strftime("%Y-%m-%d")
        moc_content = (
            f"---\n"
            f"created: {today_str}\n"
            f"updated: {today_str}\n"
            f"type: moc\n"
            f"category: {clean_id}\n"
            f"tags: [moc, {clean_id}, domain]\n"
            f"---\n\n"
            f"# 📁 MOC — {name}\n\n"
            f"Volver a: [[HOME|🏛️ HOME Master Index]]\n\n"
            f"{description or 'Base de conocimiento del dominio ' + name + '.'}\n\n"
            f"## 📑 Documentos Asociados\n"
        )
        moc_path.write_text(moc_content, encoding="utf-8")

    @staticmethod
    def _append_home_wikilink(
        vault_real: Path,
        vault_prefix: str,
        clean_id: str,
        moc_stem: str,
        name: str,
        description: str,
    ) -> None:
        home_real = os.path.realpath(os.path.join(str(vault_real), "HOME.md"))
        if not home_real.startswith(vault_prefix):
            raise ValueError("Invalid home path.")
        home_path = Path(home_real)
        if not home_path.exists():
            return
        home_text = home_path.read_text(encoding="utf-8")
        link_entry = f"\n* [[{clean_id}/{moc_stem}|📁 {clean_id} — {name}]]: {description or name}"
        if f"[[{clean_id}/" not in home_text:
            home_path.write_text(home_text.strip() + "\n" + link_entry + "\n", encoding="utf-8")

    @classmethod
    def create_domain(
        cls,
        vault_root: Path,
        domain_id: str,
        name: str,
        description: str = "",
    ) -> KnowledgeDomain:
        """
        Create a new domain directory, initialize its MOC file,
        and update HOME.md with the new wikilink.
        """
        clean_id, vault_prefix, resolved_vault, domain_dir, moc_path = cls._resolve_safe_domain_paths(
            vault_root, domain_id
        )
        domain_dir.mkdir(parents=True, exist_ok=True)
        cls._ensure_moc_file(moc_path, clean_id, name, description)
        cls._append_home_wikilink(resolved_vault, vault_prefix, clean_id, moc_path.stem, name, description)

        moc_rel = moc_path.relative_to(resolved_vault).as_posix()
        doc_count = len(list(domain_dir.rglob("*.md")))
        return KnowledgeDomain(
            id=clean_id,
            name=name,
            description=description,
            path=clean_id,
            moc_file=moc_rel,
            document_count=doc_count,
            is_system=clean_id in CORE_DOMAINS,
        )

