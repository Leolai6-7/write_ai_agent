"""Tests for BaseAgent."""

from config.models import JudgementResult
from agents.base_agent import BaseAgent


class DummyAgent(BaseAgent):
    """Concrete agent for testing."""
    def run(self, **kwargs):
        return self.call_llm(
            messages=[{"role": "user", "content": "test"}],
            **kwargs,
        )


def test_base_agent_call_llm(mock_llm):
    agent = DummyAgent(llm=mock_llm, model="mock", name="test_agent")
    result = agent.run()
    assert result == "Mock LLM response"
    assert len(mock_llm._call_log) == 1


def test_base_agent_structured_output(mock_llm):
    agent = DummyAgent(llm=mock_llm, model="mock")
    result = agent.run(response_model=JudgementResult)
    assert isinstance(result, JudgementResult)
    assert 0 <= result.overall_score <= 10


def test_base_agent_tracks_usage(mock_llm):
    agent = DummyAgent(llm=mock_llm, model="mock")
    agent.run()
    agent.run()
    assert len(mock_llm.total_usage) == 2
    assert mock_llm.get_total_cost() > 0
