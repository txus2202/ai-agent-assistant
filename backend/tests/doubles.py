"""
Shared LLM test doubles for the ai-agent-assistant backend test suite.

These are concrete implementations of domain ports used exclusively in tests.
Import them explicitly in test files that need them:

    from tests.doubles import FixedResponseProvider, FailingProvider
"""
from src.domain.exceptions import LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider


class FixedResponseProvider(ILLMProvider):
    """LLM adapter that always returns a fixed string. Use for happy-path tests."""

    def __init__(self, response: str = "42") -> None:
        self._response = response

    def complete(self, prompt: str, model_name: str) -> str:
        return self._response


class FailingProvider(ILLMProvider):
    """LLM adapter that always raises LLMProviderError. Use for failure tests."""

    def __init__(self, message: str = "quota exceeded") -> None:
        self._message = message

    def complete(self, prompt: str, model_name: str) -> str:
        raise LLMProviderError(self._message)
