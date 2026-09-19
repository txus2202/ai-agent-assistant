import pytest
from uuid import UUID
from src.domain.entities.agent import Agent, AgentStatus

def test_should_create_valid_agent():
    agent = Agent(
        name="Annotator", 
        role="Documentation specialist", 
        provider="gemini", 
        model_name="gemini-3.6-flash"
    )
    assert isinstance(agent.id, UUID)
    assert agent.name == "Annotator"
    assert agent.provider == "gemini"
    assert agent.model_name == "gemini-3.6-flash"
    assert agent.status == AgentStatus.IDLE

def test_should_fail_when_provider_is_empty():
    with pytest.raises(ValueError, match="Provider cannot be empty"):
        Agent(name="DevOps", role="Ops", provider="", model_name="gpt-4o")