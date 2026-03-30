"""Tests for JudgeAgent including voting and pairwise comparison."""

from config.models import ChapterObjective, JudgementResult
from agents.judge_agent import JudgeAgent
from prompts.loader import PromptTemplate
from tests.conftest import MockLLMClient

_JUDGE_PROMPT = PromptTemplate(
    system="Judge this chapter. Respond in JSON.",
    user="Chapter {chapter_id}: {title}\n{chapter_text}",
)


def _make_objective():
    return ChapterObjective(
        chapter_id=1, title="test", objective="test objective",
        key_events=["event"], characters_involved=["hero"],
        emotional_tone="tense",
    )


def test_single_judge():
    llm = MockLLMClient()
    judge = JudgeAgent(llm=llm, model="mock", prompt=_JUDGE_PROMPT, voting_rounds=1)
    result = judge.run("chapter text", _make_objective())
    assert isinstance(result, JudgementResult)
    assert len(llm._call_log) == 1


def test_voted_judge_3_rounds():
    llm = MockLLMClient()
    judge = JudgeAgent(llm=llm, model="mock", prompt=_JUDGE_PROMPT, voting_rounds=3)
    result = judge.run("chapter text", _make_objective())
    assert isinstance(result, JudgementResult)
    assert len(llm._call_log) == 3


def test_voted_judge_averages_scores():
    llm = MockLLMClient()
    judge = JudgeAgent(llm=llm, model="mock", prompt=_JUDGE_PROMPT, voting_rounds=3)
    result = judge.run("chapter text", _make_objective())
    assert result.overall_score == 7.5


def test_pairwise_compare():
    llm = MockLLMClient(responses={"草稿 A": "A"})
    judge = JudgeAgent(llm=llm, model="mock", prompt=_JUDGE_PROMPT)
    winner = judge.compare("draft A content", "draft B content", _make_objective())
    assert winner == "draft A content"


def test_pairwise_compare_picks_b():
    llm = MockLLMClient(responses={"草稿 A": "B"})
    judge = JudgeAgent(llm=llm, model="mock", prompt=_JUDGE_PROMPT)
    winner = judge.compare("draft A", "draft B", _make_objective())
    assert winner == "draft B"
