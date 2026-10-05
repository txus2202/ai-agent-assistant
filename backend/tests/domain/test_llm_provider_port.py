"""
RED tests for the ILLMProvider domain port and LLMProviderError exception.

Spec: obsidian_vault/docs/features/feature_llm_provider_port.md
Phase: 1 | Layer: Domain
"""
import pytest

from src.domain.ports.llm_provider import ILLMProvider
from src.domain.exceptions import LLMProviderError


# ---------------------------------------------------------------------------
# Helpers: concrete test doubles
# ---------------------------------------------------------------------------

class _WorkingAdapter(ILLMProvider):
    """Minimal adapter that satisfies the ILLMProvider contract."""

    def list_models(self) -> list[dict[str, str]]:
        return [{"id": "test", "name": "Test"}]

    def complete(self, prompt: str, model_name: str) -> str:
        return "42"


class _FailingAdapter(ILLMProvider):
    """Adapter that always raises LLMProviderError."""

    def list_models(self) -> list[dict[str, str]]:
        return [{"id": "test", "name": "Test"}]

    def complete(self, prompt: str, model_name: str) -> str:
        raise LLMProviderError("quota exceeded")


# ---------------------------------------------------------------------------
# Scenario 1: Port is abstract — cannot be instantiated directly
# ---------------------------------------------------------------------------

def test_llm_provider_port_is_abstract() -> None:
    with pytest.raises(TypeError):
        ILLMProvider()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Scenario 2: Concrete adapter satisfies the contract
# ---------------------------------------------------------------------------

def test_working_adapter_returns_non_empty_string() -> None:
    adapter = _WorkingAdapter()
    result = adapter.complete(prompt="What is the answer?", model_name="fake-v1")

    assert isinstance(result, str)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# Scenario 3: Incomplete adapter is rejected at instantiation (ABC)
# ---------------------------------------------------------------------------

def test_incomplete_adapter_raises_type_error() -> None:
    class _IncompleteAdapter(ILLMProvider):
        pass  # does NOT implement complete()

    with pytest.raises(TypeError):
        _IncompleteAdapter()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Scenario 4: LLMProviderError is a proper Exception subclass
# ---------------------------------------------------------------------------

def test_llm_provider_error_is_exception_subclass() -> None:
    error = LLMProviderError("something went wrong")

    assert isinstance(error, Exception)
    assert "something went wrong" in str(error)


# ---------------------------------------------------------------------------
# Scenario 5: Failing adapter surfaces LLMProviderError
# ---------------------------------------------------------------------------

def test_failing_adapter_raises_llm_provider_error() -> None:
    adapter = _FailingAdapter()

    with pytest.raises(LLMProviderError, match="quota exceeded"):
        adapter.complete(prompt="Hello", model_name="fake-v1")
