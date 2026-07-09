"""Evaluates generated SQL against Spider 2.0 gold SQL for demo subsets."""

import re

from askdata.schemas.spider import SpiderEvalResult


class SpiderEvaluator:
    """Computes compact demo metrics for generated SQL."""

    def Evaluate(self, predictions, goldSqlList):
        """Compares generated SQL strings with Spider gold SQL strings."""
        goldMap = {item["questionId"]: item.get("goldSql", "") for item in goldSqlList}
        exactMatch = 0
        for prediction in predictions:
            if self.Normalize(prediction.get("sql", "")) == self.Normalize(goldMap.get(prediction.get("questionId"), "")): exactMatch += 1
        return SpiderEvalResult(total=len(predictions), exactMatch=exactMatch)

    def Normalize(self, sql):
        return re.sub(r"\s+", " ", sql.strip().lower()).rstrip(";")
