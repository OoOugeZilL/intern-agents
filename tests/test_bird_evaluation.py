from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from askdata.bird.evalrunner import BirdEvalRunner, BirdResultComparer
from askdata.schemas.bird import BirdDatabase, BirdQuestion
from askdata.schemas.query import QueryResponse, TraceStep


def test_result_comparer_treats_unordered_duplicate_rows_as_equal():
    comparer = BirdResultComparer()
    left = [{"name": "A", "score": 1}, {"name": "B", "score": 2}, {"name": "A", "score": 1}]
    right = [{"score": 2, "name": "B"}, {"score": 1, "name": "A"}, {"score": 1, "name": "A"}]

    result = comparer.Compare(
        ["name", "score"],
        left,
        "select name, score from t",
        ["score", "name"],
        right,
        "select score, name from t",
    )

    assert result["passed"] is True
    assert result["mismatchType"] is None


def test_result_comparer_preserves_order_when_order_by_is_present():
    comparer = BirdResultComparer()

    result = comparer.Compare(
        ["name"],
        [{"name": "A"}, {"name": "B"}],
        "select name from t order by name",
        ["name"],
        [{"name": "B"}, {"name": "A"}],
        "select name from t",
    )

    assert result["passed"] is False
    assert result["mismatchType"] == "rows_mismatch"


def test_result_comparer_normalizes_float_and_null_values():
    comparer = BirdResultComparer()

    result = comparer.Compare(
        ["ratio", "note"],
        [{"ratio": 1.00000001, "note": None}],
        "select ratio, note from t",
        ["ratio", "note"],
        [{"ratio": 1.0, "note": None}],
        "select ratio, note from t",
    )

    assert result["passed"] is True


def test_result_comparer_reports_relaxed_pass_for_computed_alias_by_position():
    comparer = BirdResultComparer()

    result = comparer.Compare(
        ["avg_monthly_consumption"],
        [{"avg_monthly_consumption": 10.0}],
        "select avg(consumption) / 12 as avg_monthly_consumption from t",
        ["AVG(T2.Consumption) / 12"],
        [{"AVG(T2.Consumption) / 12": 10}],
        "select avg(T2.Consumption) / 12 from t",
    )

    assert result["passed"] is True
    assert result["strictPassed"] is False
    assert result["relaxedPassed"] is True
    assert result["matchMode"] == "position"


def test_result_comparer_finds_gold_values_when_generated_has_extra_columns_first():
    comparer = BirdResultComparer()

    result = comparer.Compare(
        ["total_consumption", "avg_monthly_consumption"],
        [{"total_consumption": 120, "avg_monthly_consumption": 10}],
        "select sum(consumption) as total_consumption, avg(consumption) / 12 as avg_monthly_consumption from t",
        ["AVG(T2.Consumption) / 12"],
        [{"AVG(T2.Consumption) / 12": 10}],
        "select avg(T2.Consumption) / 12 from t",
    )

    assert result["passed"] is True
    assert result["strictPassed"] is False
    assert result["relaxedPassed"] is True
    assert result["matchMode"] == "subset"


def test_result_comparer_does_not_pass_when_only_one_gold_column_name_matches():
    comparer = BirdResultComparer()

    result = comparer.Compare(
        ["id", "wrong_name"],
        [{"id": 1, "wrong_name": "bad"}],
        "select id, wrong_name from t",
        ["id", "name"],
        [{"id": 1, "name": "good"}],
        "select id, name from t",
    )

    assert result["passed"] is False
    assert result["relaxedPassed"] is False


class FakeLoader:
    def LoadProcessedQuestions(self, processedDir):
        return [
            BirdQuestion(
                questionId="q1",
                databaseId="demo",
                question="How many rows?",
                goldSql="SELECT COUNT(id) AS count FROM items",
                difficulty="simple",
            )
        ]

    def LoadProcessedDatabases(self, processedDir):
        return [BirdDatabase(databaseId="demo", databasePath=str(self.databasePath))]


class FakeQueryService:
    def RunQuery(self, request):
        assert request.sessionId == "eval-q1"
        return QueryResponse(
            question=request.question,
            databaseId=request.databaseId,
            answer="There are 2 rows.",
            sql="SELECT COUNT(id) AS count FROM items",
            executionStatus="executed",
            columns=["count"],
            rows=[{"count": 2}],
            trace=[TraceStep(step="ExecuteSql", status="success", message="Returned 1 rows.")],
        )


def test_eval_runner_reports_end_to_end_metrics(tmp_path):
    databasePath = tmp_path / "demo.sqlite"
    connection = sqlite3.connect(databasePath)
    connection.execute("CREATE TABLE items(id INTEGER)")
    connection.executemany("INSERT INTO items(id) VALUES (?)", [(1,), (2,)])
    connection.commit()
    connection.close()

    loader = FakeLoader()
    loader.databasePath = databasePath
    settings = SimpleNamespace(birdProcessedDir=tmp_path, modelName="fake-model")
    runner = BirdEvalRunner(settings=settings, loader=loader, queryService=FakeQueryService())

    report = runner.Run(limit=1)

    assert report["summary"]["total"] == 1
    assert report["summary"]["executionAccuracy"] == 1.0
    assert report["summary"]["validSqlRate"] == 1.0
    assert report["summary"]["executionSuccessRate"] == 1.0
    assert report["summary"]["answerProducedRate"] == 1.0
    assert report["byDatabase"]["demo"]["executionAccuracy"] == 1.0
    assert report["byDifficulty"]["simple"]["executionAccuracy"] == 1.0
    assert report["cases"][0]["questionId"] == "q1"
    assert report["cases"][0]["passed"] is True
    assert report["cases"][0]["generatedSql"] == "SELECT COUNT(id) AS count FROM items"
