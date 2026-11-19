"""
Architectural guard — the application/domain code must stay agnostic of the
concrete council and enforce Clean Architecture dependency boundaries.

No source file that implements generic behaviour may mention the name of any
agent shipped in the root ``agents.yaml`` (nor the built-in supervisor), nor
legacy agent-specific identifiers. If this test fails, a new coupling to the
current set of agents was introduced.

Additionally, the AST Dependency Rule guard ensures no new violations against
``domain <- application <- infrastructure/presentation`` are introduced while
tracking known Phase 4 refactor baseline items in warning mode (unless
``STRICT_ARCH_GUARD=1`` is set).
"""
from __future__ import annotations

import ast
import os
import warnings
from pathlib import Path

import pytest

from src.infrastructure.config.yaml_agent_catalog import load_profiles_from_file

BACKEND = Path(__file__).resolve().parents[3]
SRC = BACKEND / "src"
ROOT = BACKEND.parent

GENERIC_SOURCES = [
    "src/application/agents/supervisor_agent.py",
    "src/application/agents/triage_service.py",
    "src/application/agents/consolidation_service.py",
    "src/application/agents/debate_phases.py",
    "src/application/agents/debate_state.py",
    "src/application/agents/sub_agent_runner.py",
    "src/domain/agents/debate_topology.py",
    "src/domain/agents/supervisor_events.py",
    "src/presentation/api/ws/debate.py",
    "src/presentation/api/ws/learning_command_parser.py",
    "src/presentation/api/ws/debate_learning.py",
    "src/presentation/api/ws/debate_observability_tracker.py",
    "src/presentation/api/ws/wake_word.py",
    "src/presentation/api/routes/config.py",
    "src/presentation/api/config.py",
    "src/infrastructure/audio/local_audio_service.py",
    "src/infrastructure/audio/wake_word_service.py",
]

LEGACY_IDENTIFIERS = ["skip_hermes", "sphinx_critiques", "judge_history", "judge_content", "AgentRole"]

LAYER_FORBIDDEN_IMPORTS: dict[str, frozenset[str]] = {
    "domain": frozenset({
        "yaml",
        "os",
        "fastapi",
        "pydantic",
        "pydantic_settings",
        "chromadb",
        "sqlite3",
        "httpx",
        "openai",
        "anthropic",
        "google",
        "src.application",
        "src.infrastructure",
        "src.presentation",
    }),
    "application": frozenset({
        "src.infrastructure",
        "src.presentation",
        "fastapi",
        "pydantic",
        "pydantic_settings",
        "chromadb",
        "sqlite3",
    }),
    "infrastructure": frozenset({
        "src.presentation",
        "fastapi",
    }),
}

# Strict mode enforced in CI: zero Clean Architecture baseline exemptions remain.
STRICT_PROMPT_MODULES = (
    "src/application/agents/supervisor_agent.py",
    "src/application/agents/triage_service.py",
    "src/application/agents/consolidation_service.py",
    "src/application/agents/debate_phases.py",
)


def _shipped_agent_names() -> list[str]:
    catalog = load_profiles_from_file(ROOT / "agents.yaml")
    return [p.display_name for p in catalog]


def _resolve_relative_import(file_path: Path, level: int, module: str | None) -> str:
    rel_parts = list(file_path.relative_to(BACKEND).with_suffix("").parts)
    package_parts = rel_parts[:-1]
    anchor_len = max(0, len(package_parts) - (level - 1))
    base_parts = package_parts[:anchor_len]
    if module:
        return ".".join([*base_parts, module])
    return ".".join(base_parts)


def _collect_layer_dependency_violations() -> set[tuple[str, str]]:
    violations: set[tuple[str, str]] = set()
    for layer, forbidden in LAYER_FORBIDDEN_IMPORTS.items():
        layer_dir = SRC / layer
        if not layer_dir.exists():
            continue
        for py_file in sorted(layer_dir.rglob("*.py")):
            rel_path = py_file.relative_to(SRC).as_posix()
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
            for node in ast.walk(tree):
                imported_modules: list[str] = []
                if isinstance(node, ast.Import):
                    imported_modules = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level and node.level > 0:
                        resolved = _resolve_relative_import(py_file, node.level, node.module)
                        if resolved:
                            imported_modules = [resolved]
                    elif node.module:
                        imported_modules = [node.module]
                for mod in imported_modules:
                    top = mod.split(".")[0]
                    prefix2 = ".".join(mod.split(".")[:2])
                    if top in forbidden or prefix2 in forbidden:
                        violations.add((rel_path, mod))
    return violations


@pytest.mark.parametrize("relative_path", GENERIC_SOURCES)
def test_generic_sources_do_not_mention_concrete_agents(relative_path: str):
    source = (BACKEND / relative_path).read_text(encoding="utf-8")
    for name in _shipped_agent_names():
        assert name not in source, f"{relative_path} is coupled to agent '{name}'"
    for ident in LEGACY_IDENTIFIERS:
        assert ident not in source, f"{relative_path} contains legacy identifier '{ident}'"


def test_profiles_module_contains_no_concrete_agents_or_builtin_supervisor():
    source = (BACKEND / "src/domain/agents/sub_agent_profiles.py").read_text(encoding="utf-8")
    assert "BUILTIN_SUPERVISOR" not in source
    catalog_names = [p.display_name for p in load_profiles_from_file(ROOT / "agents.yaml")]
    for name in catalog_names:
        assert name not in source, f"sub_agent_profiles.py is coupled to agent '{name}'"
    for ident in (
        "_SENIOR_ARCHITECT",
        "_THE_JUDGE",
        "_DEVOPS_SECOPS",
        "_DIAGRAMMER",
        "_REGISTRY_MAP",
        "_ALL_PROFILES",
        "fidias",
        "fídias",
        "AgentRole",
    ):
        assert ident not in source


def test_supervisor_agent_prompts_are_domain_neutral():
    for rel_path in STRICT_PROMPT_MODULES:
        source = (BACKEND / rel_path).read_text(encoding="utf-8")
        for domain_word in ("arquitect", "Redis"):
            assert domain_word.lower() not in source.lower(), (
                f"domain word '{domain_word}' found in {rel_path}"
            )


def test_clean_architecture_dependency_rule_ast():
    actual = sorted(_collect_layer_dependency_violations())
    assert not actual, (
        "Clean Architecture dependency rule violations detected (strict AST guard):\n"
        + "\n".join(f"  - {path} imports '{mod}'" for path, mod in actual)
    )


def test_no_silent_broad_except_pass_ast():
    offenders: list[str] = []
    for py_file in sorted(SRC.rglob("*.py")):
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                is_bare = node.type is None
                is_exception = isinstance(node.type, ast.Name) and node.type.id in ("Exception", "BaseException")
                if is_bare or is_exception:
                    rel = py_file.relative_to(SRC).as_posix()
                    offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        "Silent broad 'except Exception: pass' blocks are forbidden; log or handle explicitly:\n"
        + "\n".join(f"  - {loc}" for loc in offenders)
    )
