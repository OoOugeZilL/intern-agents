"""Defines request and response schemas for natural-language data queries."""

from typing import Any, Literal

from pydantic import BaseModel


class QueryRequest(BaseModel):
    """Represents one natural-language data question from the frontend."""

    question: str
    sessionId: str = "default"
    databaseId: str
    showSql: bool = True
    showTrace: bool = True


class TraceStep(BaseModel):
    """Represents one visible backend or agent step."""

    step: str
    status: str
    message: str = ""


class ErrorInfo(BaseModel):
    """Represents a stable API error payload."""

    code: str
    message: str


class ChartSpec(BaseModel):
    """Represents a frontend chart recommendation."""

    chartType: Literal["table", "bar", "line", "pie", "horizontalBar"] = "table"
    title: str = "Result"
    xField: str | None = None
    yField: str | None = None
    reason: str = ""


class QueryResponse(BaseModel):
    """Represents the stable response returned by QueryService and API routes."""

    question: str
    databaseId: str
    answer: str = ""
    sql: str | None = None
    executionStatus: str = "notStarted"
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    chart: ChartSpec | None = None
    analysis: dict[str, Any] = {}
    trace: list[TraceStep] = []
    error: ErrorInfo | None = None
