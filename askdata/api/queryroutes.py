"""Registers query and session routes for the FastAPI app."""

from fastapi import FastAPI

from askdata.app.queryservice import QueryService
from askdata.core.errors import AppError
from askdata.schemas.query import ErrorInfo, QueryRequest, QueryResponse


def RegisterQueryRoutes(app: FastAPI, queryService: QueryService, sessionStore):
    """Registers query execution and session reset routes."""

    @app.post("/api/query")
    def Query(request: QueryRequest):
        try:
            return queryService.RunQuery(request)
        except AppError as error:
            return QueryResponse(question=request.question, databaseId=request.databaseId, error=ErrorInfo(code=error.__class__.__name__, message=str(error)))

    @app.post("/api/sessions/{sessionId}/reset")
    def ResetSession(sessionId: str):
        sessionStore.Reset(sessionId)
        return {"ok": True}

