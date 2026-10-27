"""
Infrastructure: Spanish Technical Phonetic Normalizer

Preprocesses text before speech synthesis (Kokoro TTS with lang='es').
Translates common English development jargon, tool names, and Greek agent archetypes
into their natural Spanish phonetic pronunciation, while stripping disruptive Markdown formatting.
"""
from __future__ import annotations

import re


class SpanishTechPhoneticNormalizer:
    """
    Normalizes technical terms and markdown in texts to produce natural-sounding
    audio when synthesized with Spanish TTS voices.
    """

    # Multi-word technical phrases (processed first to avoid partial single-word matches)
    PHRASE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
        (r"\bpull\s+requests?\b", "pul ricuest"),
        (r"\bcloud\s+native\b", "cláud néitiv"),
        (r"\bzero\s+trust\b", "céro trast"),
        (r"\bevent\s+driven\b", "event dríven"),
        (r"\bclean\s+architecture\b", "clín arquitéctur"),
        (r"\bopen\s+telemetry\b", "oupen telémetri"),
        (r"\bhuman\s+in\s+the\s+loop\b", "hítel"),
        (r"\bcontinuous\s+integration\b", "integración continua"),
        (r"\bcontinuous\s+deployment\b", "despliegue continuo"),
    )

    # Single-word technical terms and agent names
    TERM_REPLACEMENTS: tuple[tuple[str, str], ...] = (
        # Agents
        # (r"\bsphinx\b", "Esfinje"),
        (r"\bhefesto\b", "Efésto"),
        (r"\bhestia\b", "Éstia"),
        (r"\bhermes\b", "Érmes"),
        # Languages & Frameworks
        (r"\bfastapi\b", "fast-ápi"),
        (r"\bvue\b", "viu"),
        (r"\breact\b", "riáct"),
        (r"\bvite\b", "vait"),
        (r"\bpython\b", "páiton"),
        (r"\btypescript\b", "táipscrip"),
        (r"\bjavascript\b", "yávascrip"),
        (r"\bnode\.?js\b", "nóud yei-es"),
        (r"\bnode\b", "nóud"),
        # Infra, Databases & Tools
        (r"\bdocker\b", "dóquer"),
        (r"\bkubernetes\b", "cubérnetes"),
        (r"\bgithub\b", "guít-hab"),
        (r"\bgit\b", "guit"),
        (r"\bsqlite\b", "ese-qu-laite"),
        (r"\bpostgres(ql)?\b", "póstgres"),
        (r"\bchromadb\b", "cróma de-be"),
        (r"\bredis\b", "rédis"),
        (r"\bkafka\b", "káfca"),
        (r"\blangfuse\b", "láng-fius"),
        (r"\bprometheus\b", "promícius"),
        (r"\bgrafana\b", "grafána"),
        (r"\blinux\b", "línux"),
        # Architecture & Engineering Jargon
        (r"\bbackend\b", "baquend"),
        (r"\bfrontend\b", "fróntend"),
        (r"\bfullstack\b", "fulstac"),
        (r"\bpipelines?\b", "páiplain"),
        (r"\bdeployments?\b", "deplóiment"),
        (r"\bdeploys?\b", "deplóy"),
        (r"\bframeworks?\b", "fréimwork"),
        (r"\bmiddlewares?\b", "mídelwer"),
        (r"\bendpoints?\b", "éndpoint"),
        (r"\bcodebase\b", "cóudbeis"),
        (r"\bbranches?\b", "bránch"),
        (r"\bmerges?\b", "merch"),
        (r"\bcommits?\b", "cómit"),
        (r"\breleases?\b", "rilís"),
        (r"\bcloud\b", "cláud"),
        (r"\bserverless\b", "sérverles"),
        (r"\btokens?\b", "tóquen"),
        (r"\bclusters?\b", "clúster"),
        (r"\bcaching\b", "cáshing"),
        (r"\bcache\b", "caché"),
        (r"\bspofs?\b", "espof"),
        (r"\bhitl\b", "hítel"),
        (r"\bwebsockets?\b", "web-sóquet"),
        (r"\bdevsecops\b", "dev-sec-ops"),
        (r"\bdevops\b", "dev-ops"),
        (r"\bapis?\b", "ápi"),
    )

    def __init__(self) -> None:
        self._compiled_phrases = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.PHRASE_REPLACEMENTS
        ]
        self._compiled_terms = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self.TERM_REPLACEMENTS
        ]

    def strip_markdown(self, text: str) -> str:
        """Remove Markdown formatting that should not be spoken aloud."""
        # Remove fenced code blocks
        text = re.sub(r"```[\s\S]*?```", "", text)
        # Inline code
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # Images: ![alt](url) -> alt
        text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
        # Links: [text](url) -> text
        text = re.sub(r"\[([^\]]*)\]\([^)]+\)", r"\1", text)
        # Headers: ## Header -> Header
        text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
        # Bold & Italic: **text**, *text*, __text__, _text_
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        text = re.sub(r"__([^_]+)__", r"\1", text)
        text = re.sub(r"_([^_]+)_", r"\1", text)
        # Blockquotes and list markers
        text = re.sub(r"^[>\-\*]\s+", "", text, flags=re.MULTILINE)
        # Collapse multiple spaces and strip
        return re.sub(r"[ \t]+", " ", text).strip()

    def normalize(self, text: str) -> str:
        """
        Normalize Markdown and technical terminology in `text` for Spanish speech synthesis.
        """
        if not text or not text.strip():
            return ""

        # Step 1: Strip Markdown structure
        cleaned = self.strip_markdown(text)

        # Step 2: Replace multi-word technical phrases
        for pattern, replacement in self._compiled_phrases:
            cleaned = pattern.sub(replacement, cleaned)

        # Step 3: Replace single technical terms and agent names
        for pattern, replacement in self._compiled_terms:
            cleaned = pattern.sub(replacement, cleaned)

        return cleaned
