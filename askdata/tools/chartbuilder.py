"""Recommends a chart specification for frontend rendering."""

from askdata.schemas.query import ChartSpec


class ChartBuilder:
    """Builds a simple chart recommendation from result shape and question text."""

    def Build(self, question, columns, rows):
        """Returns a ChartSpec for frontend rendering."""
        if not rows or not columns: return ChartSpec(chartType="table", title="Result", reason="No rows or columns to chart.")
        lowerQuestion = question.lower()
        numericColumns = [column for column in columns if self.IsNumeric(rows[0].get(column))]
        timeColumns = [column for column in columns if any(token in column.lower() for token in ["date", "time", "year", "month"])]
        categoryColumns = [column for column in columns if column not in numericColumns]
        if len(rows) == 1 and len(columns) == 1: return ChartSpec(chartType="table", title="Result", yField=columns[0], reason="Single aggregate value.")
        if timeColumns and numericColumns: return ChartSpec(chartType="line", title="Trend", xField=timeColumns[0], yField=numericColumns[0], reason="Time field with numeric values.")
        if any(token in lowerQuestion for token in ["top", "rank", "highest", "lowest"]) and categoryColumns and numericColumns: return ChartSpec(chartType="horizontalBar", title="Ranking", xField=categoryColumns[0], yField=numericColumns[0], reason="Ranking question with category and value.")
        if categoryColumns and numericColumns: return ChartSpec(chartType="bar", title="Comparison", xField=categoryColumns[0], yField=numericColumns[0], reason="Category field with numeric values.")
        return ChartSpec(chartType="table", title="Result", reason="Table display is the safest fit.")

    def IsNumeric(self, value):
        return isinstance(value, int | float) and not isinstance(value, bool)
