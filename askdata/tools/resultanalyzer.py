"""Builds a short deterministic summary from SQL result rows."""


class ResultAnalyzer:
    """Builds compact summaries from tabular query results."""

    def Analyze(self, question, columns, rows):
        """Returns row count and a short deterministic summary."""
        if not rows: return {"rowCount": 0, "summary": "The query returned no rows."}
        if len(rows) == 1 and len(columns) == 1: return {"rowCount": 1, "summary": f"The result is {rows[0].get(columns[0])}."}
        return {"rowCount": len(rows), "summary": f"The query returned {len(rows)} rows."}

