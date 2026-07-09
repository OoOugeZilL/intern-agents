"""Defines normalized Spider 2.0 dataset schemas used by preparation and retrieval."""

from pydantic import BaseModel


class SpiderColumn(BaseModel):
    """Represents one normalized Spider column."""

    tableName: str
    columnName: str
    columnType: str = "text"
    isPrimary: bool = False


class SpiderTable(BaseModel):
    """Represents one normalized Spider table."""

    tableName: str
    columns: list[SpiderColumn] = []


class SpiderDatabase(BaseModel):
    """Represents one normalized Spider database schema."""

    databaseId: str
    tables: list[SpiderTable] = []
    primaryKeys: list[dict[str, str]] = []
    foreignKeys: list[dict[str, str]] = []


class SpiderQuestion(BaseModel):
    """Represents one Spider question and optional gold SQL."""

    questionId: str
    databaseId: str
    question: str
    goldSql: str = ""
    split: str = "demo"


class SpiderPrepareResult(BaseModel):
    """Represents the output counts from Spider data preparation."""

    databaseCount: int
    questionCount: int
    demoQuestionCount: int


class SpiderEvalResult(BaseModel):
    """Represents compact Spider demo evaluation metrics."""

    total: int
    exactMatch: int
    executionPassed: int = 0
    validationPassed: int = 0

