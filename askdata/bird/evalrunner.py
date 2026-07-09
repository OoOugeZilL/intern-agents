"""Runs end-to-end BIRD evaluation for the AskData agent."""

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from itertools import combinations
import json
import random
import re
import time

from sqlalchemy import text
from tqdm import tqdm

from askdata.app.queryservice import QueryService
from askdata.app.sessionstore import SessionStore
from askdata.bird.birdloader import BirdLoader
from askdata.core.config import LoadSettings
from askdata.db.engine import CreateEngine
from askdata.schemas.query import QueryRequest
from askdata.tools.sqlvalidator import SqlValidator


class BirdResultComparer:
    """Compares generated SQL results with gold SQL results."""

    def Compare(self, generatedColumns, generatedRows, generatedSql, goldColumns, goldRows, goldSql):
        """Returns a compact result-equivalence verdict.

        Tries column-name matching first; falls back to position-based matching
        when gold columns are unnamed computed expressions (common in BIRD gold SQL)."""
        if not goldColumns:
            passed = len(generatedRows) == 0
            return self.BuildVerdict(passed, passed, "strict" if passed else None, None if passed else "rows_mismatch")

        strictPassed = self.CompareProjectedRows(
            [self.NormalizeRow(row) for row in generatedRows],
            [self.NormalizeRow(row) for row in goldRows],
            generatedSql,
            goldSql,
        ) if set(str(c).lower() for c in (generatedColumns or [])) == set(str(c).lower() for c in goldColumns) else False

        generatedSet = set(str(c).lower() for c in (generatedColumns or []))
        sharedByName = [c for c in goldColumns if str(c).lower() in generatedSet]
        relaxedPassed = False
        matchMode = None

        if len(sharedByName) == len(goldColumns):
            generated = [self.NormalizeSubRow(row, sharedByName) for row in generatedRows]
            gold = [self.NormalizeSubRow(row, sharedByName) for row in goldRows]
            relaxedPassed = self.CompareProjectedRows(generated, gold, generatedSql, goldSql)
            matchMode = "name" if relaxedPassed else None

        if not relaxedPassed and len(generatedColumns or []) >= len(goldColumns):
            genList = list(generatedColumns)
            generated = [tuple(self.NormalizeValue(row.get(genList[i])) for i in range(len(goldColumns))) for row in generatedRows]
            gold = [tuple(self.NormalizeValue(row.get(col)) for col in goldColumns) for row in goldRows]
            relaxedPassed = self.CompareProjectedRows(generated, gold, generatedSql, goldSql)
            matchMode = "position" if relaxedPassed else None

        if not relaxedPassed and len(generatedColumns or []) > len(goldColumns):
            relaxedPassed = self.CompareGeneratedSubsets(generatedColumns, generatedRows, goldColumns, goldRows, generatedSql, goldSql)
            matchMode = "subset" if relaxedPassed else None

        passed = strictPassed or relaxedPassed
        mismatchType = None if passed else "rows_mismatch" if len(generatedColumns or []) >= len(goldColumns) else "columns_no_overlap"
        return self.BuildVerdict(strictPassed, relaxedPassed, matchMode or ("strict" if strictPassed else None), mismatchType)

    def NormalizeSubRow(self, row, columns):
        return tuple(self.NormalizeValue(row.get(col)) for col in columns)

    def CompareGeneratedSubsets(self, generatedColumns, generatedRows, goldColumns, goldRows, generatedSql, goldSql):
        gold = [tuple(self.NormalizeValue(row.get(col)) for col in goldColumns) for row in goldRows]
        for subset in combinations(generatedColumns, len(goldColumns)):
            generated = [tuple(self.NormalizeValue(row.get(col)) for col in subset) for row in generatedRows]
            if self.CompareProjectedRows(generated, gold, generatedSql, goldSql):
                return True
        return False

    def CompareProjectedRows(self, generated, gold, generatedSql, goldSql):
        if self.HasOrderBy(generatedSql) or self.HasOrderBy(goldSql):
            return generated == gold
        return Counter(generated) == Counter(gold)

    def BuildVerdict(self, strictPassed, relaxedPassed, matchMode, mismatchType):
        passed = strictPassed or relaxedPassed
        return {
            "passed": passed,
            "strictPassed": strictPassed,
            "relaxedPassed": relaxedPassed,
            "matchMode": matchMode,
            "mismatchType": None if passed else mismatchType,
        }

    def NormalizeRow(self, row):
        return tuple((str(key).lower(), self.NormalizeValue(value)) for key, value in sorted((row or {}).items()))

    def NormalizeValue(self, value):
        if value is None:
            return ("null", None)
        if isinstance(value, bool):
            return ("bool", value)
        if isinstance(value, int):
            return ("number", float(value))
        if isinstance(value, float):
            return ("number", round(value, 6))
        textValue = str(value).strip()
        try:
            return ("number", round(float(textValue), 6))
        except ValueError:
            return ("text", textValue)

    def HasOrderBy(self, sql):
        return bool(re.search(r"\border\s+by\b", sql or "", re.I))


class BirdEvalRunner:
    """Runs AskData against BIRD questions and writes evaluation reports."""

    def __init__(self, settings=None, loader=None, queryService=None, validator=None, comparer=None):
        self.settings = settings or LoadSettings()
        self.loader = loader or BirdLoader()
        self.queryService = queryService or QueryService(sessionStore=SessionStore(), settings=self.settings, loader=self.loader)
        self.validator = validator or SqlValidator()
        self.comparer = comparer or BirdResultComparer()

    def Run(self, databaseId=None, limit=None, out=None, seed=None):
        """Runs end-to-end BIRD evaluation and optionally writes a JSON report."""
        startedAt = datetime.now(UTC)
        databases = self.loader.LoadProcessedDatabases(self.settings.birdProcessedDir)
        databasePaths = {database.databaseId: database.databasePath for database in databases}
        questions = [question for question in self.loader.LoadProcessedQuestions(self.settings.birdProcessedDir) if question.goldSql]
        if databaseId:
            questions = [question for question in questions if question.databaseId == databaseId]
        if seed is not None:
            random.Random(seed).shuffle(questions)
        if limit:
            questions = questions[:limit]

        cases = [self.EvaluateQuestion(question, databasePaths.get(question.databaseId, "")) for question in tqdm(questions, desc="eval", unit="q")]
        finishedAt = datetime.now(UTC)
        report = {
            "summary": self.BuildSummary(cases, startedAt, finishedAt),
            "byDatabase": self.BuildBreakdown(cases, "databaseId"),
            "byDifficulty": self.BuildBreakdown(cases, "difficulty"),
            "cases": cases,
        }
        if out:
            path = Path(out)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return report

    def EvaluateQuestion(self, question, databasePath):
        started = time.perf_counter()
        generatedSql = ""
        answer = ""
        trace = []
        error = None
        validSql = False
        executionSucceeded = False
        passed = False
        strictPassed = False
        relaxedPassed = False
        exactMatch = False
        mismatchType = None
        matchMode = None
        generatedRows = []
        generatedColumns = []
        goldRows = []
        goldColumns = []

        try:
            response = self.queryService.RunQuery(QueryRequest(question=question.question, databaseId=question.databaseId, sessionId=f"eval-{question.questionId}", showSql=True, showTrace=True))
            generatedSql = response.sql or ""
            answer = response.answer or ""
            trace = [self.DumpTraceStep(step) for step in response.trace]
            generatedRows = response.rows[:20]
            generatedColumns = response.columns
            if not generatedSql:
                mismatchType = "empty_prediction"
            else:
                validation = self.validator.Validate(generatedSql)
                validSql = validation.valid
                if not validation.valid:
                    mismatchType = "validation_error"
                    error = validation.message
                elif response.executionStatus != "executed":
                    mismatchType = "execution_error"
                    error = error or "SQL did not execute successfully"
                else:
                    goldResult = self.ExecuteSql(question.goldSql, databasePath)
                    executionSucceeded = True
                    goldRows = goldResult["rows"][:20]
                    goldColumns = goldResult["columns"]
                    comparison = self.comparer.Compare(response.columns, response.rows, generatedSql, goldResult["columns"], goldResult["rows"], question.goldSql)
                    passed = comparison["passed"]
                    strictPassed = comparison["strictPassed"]
                    relaxedPassed = comparison["relaxedPassed"]
                    matchMode = comparison["matchMode"]
                    mismatchType = comparison["mismatchType"]
                    exactMatch = self.NormalizeSql(generatedSql) == self.NormalizeSql(question.goldSql)
        except Exception as exc:
            error = str(exc)
            if not mismatchType:
                mismatchType = "execution_error" if generatedSql else "empty_prediction"

        latencyMs = round((time.perf_counter() - started) * 1000, 2)
        retryOrRepair = any(step.get("status") == "retry" or "repair" in step.get("step", "").lower() for step in trace)
        return {
            "questionId": question.questionId,
            "databaseId": question.databaseId,
            "difficulty": question.difficulty or "unknown",
            "question": question.question,
            "goldSql": question.goldSql,
            "goldColumns": goldColumns,
            "goldRows": goldRows,
            "generatedSql": generatedSql,
            "generatedColumns": generatedColumns,
            "generatedRows": generatedRows,
            "answer": answer,
            "passed": passed,
            "metrics": {
                "validSql": validSql,
                "executionSucceeded": executionSucceeded,
                "strictPass": strictPassed,
                "relaxedPass": relaxedPassed,
                "exactMatch": exactMatch,
                "answerProduced": bool(answer.strip()),
                "retryOrRepair": retryOrRepair,
                "matchMode": matchMode,
                "mismatchType": mismatchType,
            },
            "error": error,
            "latencyMs": latencyMs,
            "trace": trace,
        }

    def ExecuteSql(self, sql, databasePath):
        if not databasePath:
            raise ValueError("Missing database path for evaluation")
        engine = CreateEngine(f"sqlite:///{databasePath}")
        cleaned = (sql or "").strip().rstrip(";")
        if not re.search(r"\blimit\b", cleaned, re.I):
            cleaned += " LIMIT 1000"
        with engine.connect() as connection:
            result = connection.execute(text(cleaned))
            return {"columns": list(result.keys()), "rows": [dict(row) for row in result.mappings().all()]}

    def BuildSummary(self, cases, startedAt, finishedAt):
        total = len(cases)
        latencies = [case["latencyMs"] for case in cases]
        return {
            "total": total,
            "executionAccuracy": self.Rate(cases, lambda case: case["passed"]),
            "executionAccuracyStrict": self.Rate(cases, lambda case: case["metrics"]["strictPass"]),
            "executionAccuracyRelaxed": self.Rate(cases, lambda case: case["metrics"]["relaxedPass"]),
            "validSqlRate": self.Rate(cases, lambda case: case["metrics"]["validSql"]),
            "executionSuccessRate": self.Rate(cases, lambda case: case["metrics"]["executionSucceeded"]),
            "exactMatchRate": self.Rate(cases, lambda case: case["metrics"]["exactMatch"]),
            "answerProducedRate": self.Rate(cases, lambda case: case["metrics"]["answerProduced"]),
            "retryRepairRate": self.Rate(cases, lambda case: case["metrics"]["retryOrRepair"]),
            "latencyMs": {
                "avg": round(sum(latencies) / total, 2) if total else 0,
                "p50": self.Percentile(latencies, 50),
                "p95": self.Percentile(latencies, 95),
            },
            "startedAt": startedAt.isoformat(),
            "finishedAt": finishedAt.isoformat(),
            "modelName": getattr(self.settings, "modelName", ""),
        }

    def BuildBreakdown(self, cases, key):
        groups = {}
        for case in cases:
            value = case.get(key) or "unknown"
            groups.setdefault(value, []).append(case)
        return {value: self.BuildGroupSummary(items) for value, items in sorted(groups.items())}

    def BuildGroupSummary(self, cases):
        latencies = [case["latencyMs"] for case in cases]
        return {
            "total": len(cases),
            "executionAccuracy": self.Rate(cases, lambda case: case["passed"]),
            "executionAccuracyStrict": self.Rate(cases, lambda case: case["metrics"]["strictPass"]),
            "executionAccuracyRelaxed": self.Rate(cases, lambda case: case["metrics"]["relaxedPass"]),
            "executionSuccessRate": self.Rate(cases, lambda case: case["metrics"]["executionSucceeded"]),
            "avgLatencyMs": round(sum(latencies) / len(latencies), 2) if latencies else 0,
        }

    def Rate(self, cases, predicate):
        if not cases:
            return 0.0
        return round(sum(1 for case in cases if predicate(case)) / len(cases), 4)

    def Percentile(self, values, percentile):
        if not values:
            return 0
        ordered = sorted(values)
        index = round((len(ordered) - 1) * percentile / 100)
        return ordered[index]

    def NormalizeSql(self, sql):
        return re.sub(r"\s+", " ", (sql or "").strip().lower()).rstrip(";")

    def DumpTraceStep(self, step):
        if hasattr(step, "model_dump"):
            return step.model_dump()
        return dict(step)
