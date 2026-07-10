from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from askdata.agent.prompts import BuildReActSystemPrompt
from askdata.agent.prompts import BuildSqlPrompt
from askdata.agent.prompts import ClassifySqlTask


class FakeSemanticContext:
    schemaPrompt = "Table event(type TEXT, location TEXT)\nTable budget(category TEXT, spent REAL)"
    matchedTables = []


def test_sql_prompt_uses_structured_sections_and_strict_output_rules():
    prompt = BuildSqlPrompt(
        "What are the budget category of the events located at MU 215 and a guest speaker type with a 0 budget spent?",
        FakeSemanticContext(),
        {},
    )

    assert "<schema>" in prompt
    assert "</schema>" in prompt
    assert "<question>" in prompt
    assert "</question>" in prompt
    assert "<schema_linking_checklist>" in prompt
    assert "never guess thresholds" in prompt
    assert "final computed value" in prompt
    assert "SELECT list must include every attribute explicitly requested by the question" in prompt
    assert "even if that attribute is also used in WHERE" in prompt
    assert "DISTINCT:" in prompt
    assert "Never split a single identifier" in prompt
    assert "<schema_linking_checklist>" in prompt
    assert "select columns" in prompt
    assert "filter columns" in prompt
    assert "literal values" in prompt
    assert "<task_type>" in prompt


class FakeMatchedTable:
    def __init__(self, tableName):
        self.tableName = tableName


class FakeJoinContext:
    schemaPrompt = "Table event(event_id TEXT, type TEXT)\nTable budget(category TEXT, link_to_event TEXT)\nJoin budget.link_to_event = event.event_id"
    matchedTables = [FakeMatchedTable("event"), FakeMatchedTable("budget")]


class FakeSingleTableContext:
    schemaPrompt = "Table classroom(building TEXT, capacity INTEGER)"
    matchedTables = [FakeMatchedTable("classroom")]


def test_classify_sql_task_uses_schema_and_question_shape():
    assert ClassifySqlTask("Find buildings with capacity more than 50.", FakeSingleTableContext()) == "EASY"
    assert ClassifySqlTask("List event categories by guest speaker type.", FakeJoinContext()) == "NON_NESTED"
    assert ClassifySqlTask("Find instructors who taught in Fall 2009 but not in Spring 2010.", FakeSingleTableContext()) == "NESTED"


def test_sql_prompt_switches_guidance_for_non_nested_join_tasks():
    prompt = BuildSqlPrompt("List event categories by guest speaker type.", FakeJoinContext(), {})

    assert "<task_type>NON_NESTED</task_type>" in prompt
    assert "JOIN key columns must come from the schema join lines" in prompt
    assert "Do not invent join conditions" in prompt


def test_react_prompt_allows_evidence_directed_aggregation_of_precomputed_metrics():
    prompt = BuildReActSystemPrompt()

    assert "If the schema evidence defines a formula" in prompt
    assert "sum(average math scores) / count(schools)" in prompt
