"""Validates and normalizes generated SQL before execution."""

import re

import sqlglot
from sqlglot import exp

from askdata.schemas.sql import SqlValidationResult


class SqlValidator:
    """Validates generated SQL and applies small safe normalizations."""

    def Validate(self, sql, semanticContext=None):
        """Rejects unsafe SQL and returns normalized SELECT SQL with a bounded LIMIT."""
        rawSql = (sql or "").strip().rstrip(";")
        if not rawSql: return SqlValidationResult(valid=False, message="SQL is empty")
        if ";" in rawSql: return SqlValidationResult(valid=False, message="Multiple SQL statements are not allowed")
        if re.search(r"\b(insert|update|delete|drop|alter|create|truncate)\b", rawSql, re.I): return SqlValidationResult(valid=False, message="Only SELECT statements are allowed")
        try:
            parsed = sqlglot.parse_one(rawSql)
        except Exception as error:
            return SqlValidationResult(valid=False, message=f"Invalid SQL: {error}")
        if not isinstance(parsed, exp.Select): return SqlValidationResult(valid=False, message="Only SELECT statements are allowed")
        if self.HasSelectStar(rawSql): return SqlValidationResult(valid=False, message="SELECT * is not allowed")
        limitedSql = self.ApplyLimit(rawSql)
        return SqlValidationResult(valid=True, sql=limitedSql, message="SQL is valid")

    def ApplyLimit(self, sql):
        match = re.search(r"\blimit\s+(\d+)\b", sql, re.I)
        if not match: return f"{sql} LIMIT 20"
        limit = min(int(match.group(1)), 100)
        return re.sub(r"\blimit\s+\d+\b", f"LIMIT {limit}", sql, flags=re.I)

    def HasSelectStar(self, sql):
        match = re.search(r"\bselect\b(.+?)\bfrom\b", sql, re.I | re.S)
        if not match: return False
        selectPart = re.sub(r"\bcount\s*\(\s*\*\s*\)", "count()", match.group(1), flags=re.I)
        return bool(re.search(r"(^|,)\s*([\w\"`]+\.)?\*\s*(,|$)", selectPart))
