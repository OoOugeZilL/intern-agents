"""Defines normalized BIRD dataset schemas used by preparation and retrieval."""

from pydantic import BaseModel


class BirdColumn(BaseModel):
    """Represents one normalized BIRD column."""

    tableName: str
    columnName: str
    columnType: str = "text"
    isPrimary: bool = False


class BirdTable(BaseModel):
    """Represents one normalized BIRD table."""

    tableName: str
    columns: list[BirdColumn] = []


class BirdDatabase(BaseModel):
    """Represents one normalized BIRD database schema."""

    databaseId: str
    databasePath: str = ""
    tables: list[BirdTable] = []
    primaryKeys: list[dict[str, str]] = []
    foreignKeys: list[dict[str, str]] = []


class BirdQuestion(BaseModel):
    """Represents one BIRD question with optional evidence and gold SQL."""

    questionId: str
    databaseId: str
    question: str
    evidence: str | None = None
    goldSql: str | None = None
    difficulty: str | None = None
    split: str = "mini_dev_sqlite"


class BirdPrepareResult(BaseModel):
    """Represents the output counts from BIRD data preparation."""

    databaseCount: int
    questionCount: int
    demoQuestionCount: int


class BirdEvalResult(BaseModel):
    """Represents compact BIRD demo evaluation metrics."""

    total: int
    exactMatch: int
    executionPassed: int = 0
    validationPassed: int = 0
