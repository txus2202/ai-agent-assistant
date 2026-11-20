"""
Architectural guard for backend/src/domain/ports/ conventions (ADR / Audit Punto 25):
  - All port modules use clean `<concept>.py` naming (no redundant `*_port.py` suffix).
  - Every port interface (`I...`) is a `@runtime_checkable` `typing.Protocol`.
  - No `abc.ABC` or `@abstractmethod` remains in `domain/ports/`.
  - No concrete adapter/service implementation (e.g. `NoOp*`) lives in `domain/ports/`
    (only dataclasses / Enums are allowed as port DTOs/value objects).
"""
from __future__ import annotations

import ast
import importlib
from dataclasses import is_dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


PORTS_DIR = Path(__file__).resolve().parents[2] / "src" / "domain" / "ports"


def _port_files() -> list[Path]:
    return sorted(p for p in PORTS_DIR.glob("*.py") if p.name != "__init__.py")


def test_no_legacy_port_filename_suffix() -> None:
    legacy = [p.name for p in _port_files() if p.stem.endswith("_port")]
    assert legacy == [], f"Found legacy *_port.py modules: {legacy}"


def test_ports_use_runtime_checkable_protocol_without_abc() -> None:
    port_files = _port_files()
    assert len(port_files) >= 16

    for path in port_files:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))

        # Check forbidden abc / ABC / abstractmethod usage
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "abc":
                raise AssertionError(f"{path.name} must not import from abc; use typing.Protocol")
            if isinstance(node, ast.ClassDef):
                base_names = [ast.unparse(base) for base in node.bases]
                assert "ABC" not in base_names, f"{path.name}:{node.name} must use Protocol, not ABC"

        module_name = f"src.domain.ports.{path.stem}"
        module = importlib.import_module(module_name)

        defined_classes = [
            obj
            for obj in vars(module).values()
            if isinstance(obj, type) and obj.__module__ == module_name
        ]
        assert defined_classes, f"{path.name} defines no classes"

        interface_classes = []
        for cls in defined_classes:
            # Port DTOs / value objects (frozen dataclasses, Enums) are permitted alongside ports
            if is_dataclass(cls) or issubclass(cls, Enum):
                continue

            interface_classes.append(cls)
            assert cls.__name__.startswith("I"), (
                f"{path.name}:{cls.__name__} does not start with 'I' — concrete classes must live in infrastructure/"
            )
            assert getattr(cls, "_is_protocol", False) is True, (
                f"{path.name}:{cls.__name__} must be a typing.Protocol subclass"
            )
            assert Protocol in cls.__bases__, (
                f"{path.name}:{cls.__name__} must inherit directly from typing.Protocol"
            )
            assert getattr(cls, "_is_runtime_protocol", False) is True, (
                f"{path.name}:{cls.__name__} must be decorated with @runtime_checkable"
            )

        assert interface_classes, f"{path.name} must define at least one I... Protocol interface"
