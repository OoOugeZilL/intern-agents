"""Defines semantic retrieval results passed from BIRD schema indexing to the agent."""

from pydantic import BaseModel


class MatchedTable(BaseModel):
    """Represents a BIRD table selected for a query."""

    tableName: str
    reason: str = ""


class MatchedColumn(BaseModel):
    """Represents a BIRD column selected for a query."""

    tableName: str
    columnName: str
    columnType: str = "text"
    reason: str = ""


class MatchedJoin(BaseModel):
    """Represents a foreign key relation selected for a query."""

    leftTable: str
    leftColumn: str
    rightTable: str
    rightColumn: str


class SemanticContext(BaseModel):
    """Represents the schema context sent to SQL generation."""

    databaseId: str
    databasePath: str | None = None
    matchedTables: list[MatchedTable] = []
    matchedColumns: list[MatchedColumn] = []
    matchedJoins: list[MatchedJoin] = []
    schemaPrompt: str = ""
