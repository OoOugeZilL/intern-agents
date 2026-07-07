"""Registers BIRD metadata and evaluation routes for the FastAPI app."""

from fastapi import FastAPI

from askdata.bird.birdloader import BirdLoader
from askdata.bird.evaluator import BirdEvaluator
from askdata.core.config import Settings


def RegisterBirdRoutes(app: FastAPI, settings: Settings, loader=None, evaluator=None):
    """Registers BIRD database, question, and evaluation routes."""
    loader = loader or BirdLoader()
    evaluator = evaluator or BirdEvaluator()

    @app.get("/api/bird/databases")
    def Databases():
        questions = loader.LoadProcessedQuestions(settings.birdProcessedDir)
        counts = {}
        for question in questions:
            counts[question.databaseId] = counts.get(question.databaseId, 0) + 1
        return {"databases": [{"databaseId": database.databaseId, "tableCount": len(database.tables), "questionCount": counts.get(database.databaseId, 0), "databasePath": database.databasePath} for database in loader.LoadProcessedDatabases(settings.birdProcessedDir)]}

    @app.get("/api/bird/questions")
    def Questions(databaseId: str | None = None):
        questions = loader.LoadProcessedQuestions(settings.birdProcessedDir)
        if databaseId: questions = [item for item in questions if item.databaseId == databaseId]
        return {"questions": [{"questionId": item.questionId, "databaseId": item.databaseId, "question": item.question, "evidence": item.evidence, "goldSql": item.goldSql, "difficulty": item.difficulty} for item in questions]}

    @app.post("/api/bird/evaluate")
    def Evaluate(payload: dict):
        predictions = payload.get("predictions", [])
        goldSqlList = payload.get("goldSqlList", [])
        return evaluator.Evaluate(predictions, goldSqlList)
