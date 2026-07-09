"""Registers Spider 2.0 metadata and evaluation routes for the FastAPI app."""

from fastapi import FastAPI

from askdata.core.config import Settings
from askdata.core.errors import AppError
from askdata.spider.evaluator import SpiderEvaluator
from askdata.spider.spiderloader import SpiderLoader


def RegisterSpiderRoutes(app: FastAPI, settings: Settings, loader=None, evaluator=None):
    """Registers Spider database, question, and evaluation routes."""
    loader = loader or SpiderLoader()
    evaluator = evaluator or SpiderEvaluator()

    @app.get("/api/spider/databases")
    def Databases():
        try:
            questions = loader.LoadProcessedQuestions(settings.spiderProcessedDir)
            counts = {}
            for question in questions:
                counts[question.databaseId] = counts.get(question.databaseId, 0) + 1
            return {"databases": [{"databaseId": database.databaseId, "tableCount": len(database.tables), "questionCount": counts.get(database.databaseId, 0)} for database in loader.LoadProcessedDatabases(settings.spiderProcessedDir)]}
        except AppError as error:
            return {"databases": [], "error": {"code": error.__class__.__name__, "message": str(error)}}

    @app.get("/api/spider/questions")
    def Questions(databaseId: str | None = None):
        try:
            questions = loader.LoadProcessedQuestions(settings.spiderProcessedDir)
            if databaseId: questions = [question for question in questions if question.databaseId == databaseId]
            return {"questions": [question.model_dump() for question in questions]}
        except AppError as error:
            return {"questions": [], "error": {"code": error.__class__.__name__, "message": str(error)}}

    @app.post("/api/spider/evaluate")
    def Evaluate(payload: dict):
        return evaluator.Evaluate(payload.get("predictions", []), payload.get("goldSqlList", [])).model_dump()

