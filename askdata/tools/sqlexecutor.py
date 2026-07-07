"""Executes validated SQL and returns tabular results."""

from sqlalchemy import text

from askdata.core.errors import SqlError
from askdata.db.engine import CreateEngine
from askdata.schemas.sql import SqlExecutionResult


class SqlExecutor:
    """Executes validated SQL against a configured SQLAlchemy database URL."""

    def Execute(self, sql, databaseUrl):
        """Runs SQL and returns columns plus row dictionaries."""
        try:
            engine = CreateEngine(databaseUrl)
            with engine.connect() as connection:
                result = connection.execute(text(sql))
                rows = [dict(row) for row in result.mappings().all()]
                columns = list(result.keys())
                return SqlExecutionResult(columns=columns, rows=rows)
        except Exception as error:
            raise SqlError(f"SQL execution failed: {error}") from error
