"""Tests for ConsistencyChecker agent."""

from config.models import ConsistencyReport
from agents.consistency_checker import ConsistencyChecker
from tests.conftest import MockLLMClient


def test_consistency_checker_returns_report():
    llm = MockLLMClient()
    checker = ConsistencyChecker(llm=llm, model="mock")
    result = checker.run(
        chapter_text="伊澤走進圖書館",
        chapter_id=5,
        character_context="伊澤：位於圖書館",
        relevant_history="前四章摘要...",
    )
    assert isinstance(result, ConsistencyReport)


def test_consistency_checker_structured_output():
    responses = {
        "伊澤": {
            "is_consistent": False,
            "contradictions": [{
                "type": "character",
                "description": "伊澤在第3章失去了左臂，但此章又用雙手施法",
                "source_chapter": 3,
                "conflicting_text": "伊澤雙手結印",
                "suggested_fix": "改為單手施法",
            }],
            "warnings": ["時間線可能有跳躍"],
        }
    }
    llm = MockLLMClient(responses=responses)
    checker = ConsistencyChecker(llm=llm, model="mock")
    result = checker.run(chapter_text="伊澤雙手結印", chapter_id=5)
    assert isinstance(result, ConsistencyReport)
