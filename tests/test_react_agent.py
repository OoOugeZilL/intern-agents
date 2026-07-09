from pathlib import Path
import json
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from askdata.agent.react_agent import MAX_ITERATIONS, ReActAgent
from askdata.schemas.query import QueryRequest
from askdata.schemas.semantic import SemanticContext
from askdata.schemas.sql import SqlExecutionResult


class RepeatingToolCallLlm:
    def Chat(self, messages, tools=None):
        return SimpleNamespace(
            content=None,
            tool_calls=[
                SimpleNamespace(
                    id="call_1",
                    function=SimpleNamespace(
                        name="run_query",
                        arguments=json.dumps({"sql": "SELECT school, funding_type FROM result"}),
                    ),
                )
            ],
        )


class VerboseFinalAnswerLlm:
    def __init__(self):
        self.calls = 0

    def Chat(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return SimpleNamespace(
                content=None,
                tool_calls=[
                    SimpleNamespace(
                        id="call_1",
                        function=SimpleNamespace(
                            name="run_query",
                            arguments=json.dumps({"sql": "SELECT answer FROM result"}),
                        ),
                    )
                ],
            )
        return SimpleNamespace(
            content=(
                "The question asks: \"Is the set only available outside the United States?\"\n\n"
                "The answer is no, because none of the sets have isForeignOnly = 1.\n\n"
                "**Answer:** No."
            ),
            tool_calls=None,
        )


class FakeExecutor:
    def Execute(self, sql, databaseUrl):
        return SqlExecutionResult(
            columns=["school", "funding_type"],
            rows=[
                {"school": "Arlington High", "funding_type": None},
                {"school": "California Military Institute", "funding_type": "Locally funded"},
            ],
        )


class EmptySkillLoader:
    def BuildPromptSection(self):
        return ""


def test_agent_returns_result_summary_when_model_never_finalizes_after_successful_query():
    agent = ReActAgent(
        llmClient=RepeatingToolCallLlm(),
        executor=FakeExecutor(),
        skillLoader=EmptySkillLoader(),
    )
    request = QueryRequest(question="Which schools?", databaseId="california_schools")
    context = SemanticContext(
        databaseId="california_schools",
        databasePath="/tmp/fake.sqlite",
        schemaPrompt="Table result(school text, funding_type text)",
    )

    response = agent.Run(request, context)

    assert response.executionStatus == "executed"
    assert response.answer != "Unable to answer the question within the available steps."
    assert "Arlington High" in response.answer
    assert len([step for step in response.trace if step.step == "ExecuteSql"]) == MAX_ITERATIONS


def test_agent_strips_analysis_preface_from_final_answer():
    agent = ReActAgent(
        llmClient=VerboseFinalAnswerLlm(),
        executor=FakeExecutor(),
        skillLoader=EmptySkillLoader(),
    )
    request = QueryRequest(question="Is it foreign-only?", databaseId="card_games")
    context = SemanticContext(
        databaseId="card_games",
        databasePath="/tmp/fake.sqlite",
        schemaPrompt="Table result(answer text)",
    )

    response = agent.Run(request, context)

    assert response.answer == "No."


def test_agent_keeps_last_direct_yes_no_answer_when_analysis_appears_before_it():
    agent = ReActAgent(skillLoader=EmptySkillLoader())
    answer = agent.CleanFinalAnswer(
        "All five sets have `isForeignOnly = 0`, meaning none of them are only available outside the United States.\n\n"
        "The question asks \"Is the set of cards with Adarkar Valkyrie only available outside the United States?\" — this is a yes/no question. Since none of the sets containing Adarkar Valkyrie have `isForeignOnly = 1`, the answer is no.\n\n"
        "No, the sets containing Adarkar Valkyrie are not only available outside the United States."
    )

    assert answer == "No, the sets containing Adarkar Valkyrie are not only available outside the United States."
