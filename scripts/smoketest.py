"""Runs a minimal backend smoke test without real BIRD data or model calls."""

from pathlib import Path
from tempfile import gettempdir
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from askdata.api.main import CreateApp
from askdata.bird.birdprep import BirdPrep
from askdata.core.errors import DataError
from askdata.schemas.query import QueryRequest, QueryResponse
from askdata.schemas.semantic import SemanticContext
from askdata.tools.sqlvalidator import SqlValidator


def SmokeTest():
    """Checks core imports, schemas, SQL validation, and BIRD path failure behavior."""
    app = CreateApp()
    assert app.title == "AskData Backend"
    request = QueryRequest(question="How many accounts are there?", sessionId="default", databaseId="financial")
    response = QueryResponse(question=request.question, databaseId=request.databaseId, answer="ok")
    assert response.answer == "ok"
    context = SemanticContext(databaseId="financial", schemaPrompt="Table account(account_id integer)")
    dropResult = SqlValidator().Validate("DROP TABLE singer", context)
    assert not dropResult.valid
    limitResult = SqlValidator().Validate("SELECT account_id FROM account", context)
    assert limitResult.valid and "LIMIT 20" in limitResult.sql
    countResult = SqlValidator().Validate("SELECT COUNT(*) AS accountCount FROM account", context)
    assert countResult.valid
    starResult = SqlValidator().Validate("SELECT * FROM account", context)
    assert not starResult.valid
    try:
        tempDir = Path(gettempdir())
        BirdPrep().Prepare(Path("missing-bird-raw"), tempDir / "askdata-processed", tempDir / "askdata-demo")
    except DataError as error:
        assert "does not exist" in str(error)
    else:
        raise AssertionError("BirdPrep should fail for missing raw directory")
    print("smoke test passed")


if __name__ == "__main__":
    SmokeTest()
