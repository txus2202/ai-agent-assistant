"""
Infrastructure Adapter: ImageExtractor

Extracts structured technical Markdown descriptions from image files
(diagrams, architectural schemes, workflows) using vision-capable LLMs.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.domain.exceptions import ExtractionError

_VISION_PROMPT = """\
Eres un analizador técnico de diagramas y esquemas de software.
Analiza exhaustivamente la imagen proporcionada (diagrama, arquitectura o esquema técnico) y genera un documento Markdown estructurado con:
1. Un título descriptivo (# Título del Diagrama).
2. Resumen general de la arquitectura o flujo representado.
3. Listado detallado de componentes, subsistemas y actores identificados.
4. Conexiones, flujos de datos y protocolos indicados en el diagrama.
5. Reconstrucción textual o en sintaxis Mermaid si aplica.

Devuelve únicamente la descripción técnica estructurada en Markdown.
"""


class ImageExtractor:
    """Extracts technical knowledge from image files using multimodal LLMs."""

    @staticmethod
    def extract(
        image_path: Path,
        llm_provider: Any,
        model_name: str,
    ) -> str:
        """
        Analyze an image file and return its textual technical description.

        Args:
            image_path: Path to the image file (.png, .jpg, .jpeg, .webp).
            llm_provider: ILLMProvider instance to perform vision inference.
            model_name: Model identifier with vision capability.

        Returns:
            Structured Markdown description of the image content.

        Raises:
            ExtractionError: If the image cannot be read or LLM analysis fails.
        """
        p = Path(image_path)
        if not p.exists() or not p.is_file():
            raise ExtractionError(f"Image file not found: {image_path}")

        try:
            if hasattr(llm_provider, "complete_image"):
                return str(llm_provider.complete_image(_VISION_PROMPT, p, model_name=model_name))
            return str(llm_provider.complete(_VISION_PROMPT, model_name=model_name))
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(str(exc)) from exc

