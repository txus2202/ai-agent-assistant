"""
Application Service: LearnFromSession

Extracts architectural consensus, decisions, and lessons learned from a debate
or multi-agent chat session, saves the structured solution note into the Obsidian
vault, and ingests it into ChromaDB for long-term memory retrieval.
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.application.services.ingest_vault import IngestResult, IngestVault
from src.application.services.learn_from_source import LearnResult
from src.domain.exceptions import LLMProviderError
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.llm_provider import ILLMProvider

_SESSION_SYNTHESIS_PROMPT = """\
You are an expert technical knowledge synthesizer for multi-agent systems.
Analyze the following discussion or session history and generate a high-value architecture solution note.
Strictly adhere to this format:

1. Start with YAML frontmatter (between --- delimiters):
   - type: solution
   - created: {date} (YYYY-MM-DD)
   - tags: [solucion, arquitectura, consenso, "{session_tag}", plus 3 to 6 relevant topical tags automatically inferred from the discussion]
   - session_id: {session_id}

2. A single H1 title starting with "Solución: " or "Decisión: " summarizing the consensus in 5-10 words.

3. Structured sections:
   ## Resumen Ejecutivo
   (Concise description of the problem and the approved architecture).

   ## Decisiones Clave y Consenso
   (Bullet points citing the key proposals, trade-offs, and decisions validated by the participants).

   ## Componentes y Tecnologías
   (Technical stack, protocols, interfaces, or patterns adopted).

   ## Restricciones y Lecciones Aprendidas
   (Trade-offs, security, or performance safeguards highlighted).

Return ONLY the Markdown document with frontmatter. No extra commentary.
"""


class LearnFromSession:
    """Extracts and persists knowledge from completed sessions."""

    @staticmethod
    def run(
        session_id: str,
        chat_history: list[dict[str, Any]],
        llm_provider: ILLMProvider,
        document_store: IDocumentStore,
        vault_root: Path,
        model_name: str,
        solution_content: str | None = None,
        target_domain: str = "deliberations/sessions",
    ) -> LearnResult:
        if not chat_history and not solution_content:
            return LearnResult(
                source=session_id,
                generated_file=None,
                errors=["Historial vacío o sin contenido para aprender."],
            )

        # Build transcript representation
        lines: list[str] = []
        for msg in chat_history:
            sender = msg.get("name") or msg.get("agent") or msg.get("role", "Desconocido")
            content = msg.get("content", "")
            lines.append(f"### {sender}\n{content}")

        if solution_content:
            lines.append(f"### Dictamen Consolidado\n{solution_content}")

        transcript = "\n\n".join(lines)
        date_str = datetime.now().strftime("%Y-%m-%d")
        session_tag = f"sesion-{session_id[:8]}"

        prompt = (
            f"{_SESSION_SYNTHESIS_PROMPT.format(date=date_str, session_id=session_id, session_tag=session_tag)}\n\n"
            f"--- Transcripción de la Sesión ---\n{transcript}"
        )

        try:
            md_content = llm_provider.complete(prompt, model_name)
        except LLMProviderError as exc:
            return LearnResult(source=session_id, generated_file=None, errors=[str(exc)])

        # Derive slug
        slug = _derive_slug(md_content, fallback=f"sesion-{session_id[:8]}")
        filename = f"{date_str}_solucion_{slug}.md"

        clean_domain = target_domain.strip().strip("/") if target_domain else "deliberations/sessions"
        if ".." in clean_domain:
            clean_domain = "deliberations/sessions"
        dest_dir = vault_root / clean_domain
        dest_dir.mkdir(parents=True, exist_ok=True)
        file_path = dest_dir / filename
        file_path.write_text(md_content, encoding="utf-8")

        ingest_result = IngestVault.run(
            vault_root=vault_root,
            document_store=document_store,
        )

        return LearnResult(
            source=session_id,
            generated_file=file_path,
            ingest_result=ingest_result,
            errors=[],
        )


def _derive_slug(md_content: str, fallback: str) -> str:
    match = re.search(r"^#[ \t]+([^ \t\n].*)$", md_content, re.MULTILINE)
    raw = match.group(1).strip() if match else fallback

    slug = re.sub(r"[^\w\s-]", "", raw.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:80]
