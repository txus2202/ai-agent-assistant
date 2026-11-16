"""
Application Service: VaultDomainService

Discovers, inspects, and creates hierarchical knowledge domains within the Obsidian vault.
Encapsulates MOC (Map of Content) management and directory hygiene.
"""
from __future__ import annotations

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
    def list_domains(cls, vault_root: Path) -> list[KnowledgeDomain]:
        """Scan vault_root and return all configured and discovered knowledge domains."""
        domains: list[KnowledgeDomain] = []
        if not vault_root.exists() or not vault_root.is_dir():
            return domains

        # 1. Process known core domains first
        for domain_id, info in CORE_DOMAINS.items():
            dir_path = vault_root / domain_id
            if dir_path.is_dir():
                doc_count = len(list(dir_path.rglob("*.md")))
                moc_candidates = list(dir_path.glob("MOC_*.md"))
                moc_rel = moc_candidates[0].relative_to(vault_root).as_posix() if moc_candidates else f"{domain_id}/MOC_{domain_id}.md"

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

        # 2. Discover custom domains (top-level directories not starting with "." and not core)
        for item in sorted(vault_root.iterdir()):
            if not item.is_dir():
                continue
            if item.name.startswith(".") or item.name in CORE_DOMAINS:
                continue

            doc_count = len(list(item.rglob("*.md")))
            moc_candidates = list(item.glob("MOC_*.md"))
            moc_rel = moc_candidates[0].relative_to(vault_root).as_posix() if moc_candidates else f"{item.name}/MOC_{item.name}.md"
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
        clean_id = domain_id.strip()
        if not clean_id or not _SAFE_ID_RE.match(clean_id):
            raise ValueError(f"Invalid domain ID '{domain_id}'. Must contain only alphanumeric, '_' or '-'.")

        domain_dir = vault_root / clean_id
        domain_dir.mkdir(parents=True, exist_ok=True)

        clean_slug = clean_id.replace("-", "_")
        moc_filename = f"MOC_{clean_slug}.md"
        moc_path = domain_dir / moc_filename
        moc_rel = moc_path.relative_to(vault_root).as_posix()

        today_str = datetime.now().strftime("%Y-%m-%d")
        if not moc_path.exists():
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

        # Update HOME.md if present
        home_path = vault_root / "HOME.md"
        if home_path.exists():
            home_text = home_path.read_text(encoding="utf-8")
            link_entry = f"\n* [[{clean_id}/{moc_path.stem}|📁 {clean_id} — {name}]]: {description or name}"
            if f"[[{clean_id}/" not in home_text:
                home_path.write_text(home_text.strip() + "\n" + link_entry + "\n", encoding="utf-8")

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

