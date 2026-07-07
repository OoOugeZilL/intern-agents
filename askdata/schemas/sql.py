"""Defines SQL generation, validation, and execution result schemas."""

from typing import Any

from pydantic import BaseModel


class SqlValidationResult(BaseModel):
    """Represents SQL validation status and normalized SQL."""

    valid: bool
    sql: str = ""
    message: str = ""


class SqlExecutionResult(BaseModel):
    """Represents tabular SQL execution output."""

    columns: list[str] = []
    rows: list[dict[str, Any]] = []


class SqlGenerationResult(BaseModel):
    """Represents generated SQL text and an optional message."""

    sql: str
    message: str = ""
