"""Evaluates generated SQL against BIRD gold SQL for demo subsets."""

from askdata.schemas.bird import BirdEvalResult


class BirdEvaluator:
    """Computes compact BIRD evaluation metrics for demo predictions."""

    def Evaluate(self, predictions, goldSqlList):
        """Compares generated SQL strings with BIRD gold SQL strings."""
        total = min(len(predictions), len(goldSqlList))
        exactMatch = 0
        for index in range(total):
            if self.Normalize(predictions[index]) == self.Normalize(goldSqlList[index]): exactMatch += 1
        return BirdEvalResult(total=total, exactMatch=exactMatch)

    def Normalize(self, sql):
        return " ".join((sql or "").strip().lower().rstrip(";").split())
