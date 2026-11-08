"""
Unit tests for SpanishTechPhoneticNormalizer (TDD).
Layer: Infrastructure / Audio
"""
import pytest

from src.infrastructure.audio.phonetic_normalizer import SpanishTechPhoneticNormalizer


class TestSpanishTechPhoneticNormalizer:
    @pytest.fixture
    def normalizer(self):
        return SpanishTechPhoneticNormalizer()

    def test_normalize_common_technical_terms(self, normalizer):
        text = "Desplegamos el backend con Docker y Kubernetes usando un pipeline en FastAPI."
        result = normalizer.normalize(text)

        assert "baquend" in result.lower()
        assert "dóquer" in result.lower()
        assert "cubérnetes" in result.lower()
        assert "páiplain" in result.lower()
        assert "fast-ápi" in result.lower()

    def test_normalize_multi_word_technical_phrases(self, normalizer):
        text = "Aprobamos el pull request para la arquitectura cloud native con zero trust."
        result = normalizer.normalize(text)

        assert "pul ricuest" in result.lower()
        assert "cláud néitiv" in result.lower()
        assert "céro trast" in result.lower()

    def test_word_boundaries_prevent_false_positives(self, normalizer):
        text = "Debemos destacar esta apisonadora deprisa para evitar incidentes."
        result = normalizer.normalize(text)

        # "destacar" contains "stack", "apisonadora" contains "api"
        assert "destacar" in result
        assert "apisonadora" in result
        assert "deprisa" in result

    def test_strip_markdown_syntax_for_clean_speech(self, normalizer):
        text = "## 1. **Resumen Ejecutivo**\nRevisa el [enlace](https://example.com) y ejecuta `npm test`."
        result = normalizer.normalize(text)

        assert "##" not in result
        assert "**" not in result
        assert "https://" not in result
        assert "enlace" in result

    def test_normalize_agent_names(self, normalizer):
        text = "El veredicto de Sphinx y el dictamen de Hefesto para Hestia y Hermes."
        result = normalizer.normalize(text)

        assert "sphinx" in result.lower()
        assert "efésto" in result.lower()
        assert "éstia" in result.lower()
        assert "érmes" in result.lower()

    def test_empty_and_plain_spanish_preserved(self, normalizer):
        assert normalizer.normalize("") == ""
        assert normalizer.normalize("   ") == ""
        plain = "Buenos días, el sistema funciona correctamente."
        assert normalizer.normalize(plain) == plain

    def test_strip_fenced_code_blocks_and_tools_from_speech(self, normalizer):
        text = (
            "He generado la maquetación solicitada:\n"
            "```html\n"
            "<!DOCTYPE html>\n"
            "<html lang='es'>\n"
            "<head><style>body { background: #000; }</style></head>\n"
            "<body><div class='carousel'>Items</div></body>\n"
            "</html>\n"
            "```\n"
            "¿Qué opinas del diseño visual?"
        )
        result = normalizer.normalize(text)
        assert "<!DOCTYPE" not in result
        assert "<style>" not in result
        assert "carousel" not in result
        assert "He generado la maquetación solicitada:" in result
        assert "¿Qué opinas del diseño visual?" in result

    def test_code_only_returns_voice_fallback(self, normalizer):
        text = "```python\ndef calculate():\n    return 42\n```"
        result = normalizer.normalize(text)
        assert result == "He generado el código en pantalla."

    def test_strip_image_tags_and_directives_from_speech(self, normalizer):
        text = (
            "Diseño preparado:\n"
            "[GENERATE_IMAGE: Futuristic cyberpunk dashboard with neon violet, 8k]\n"
            "![Mockup](/api/images/fidias_test.png)\n"
            "Listo para revisión."
        )
        result = normalizer.normalize(text)
        assert "GENERATE_IMAGE" not in result
        assert "/api/images/" not in result
        assert "Diseño preparado:" in result
        assert "Listo para revisión." in result

