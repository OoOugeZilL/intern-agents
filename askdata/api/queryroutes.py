"""Registers query and session routes for the FastAPI app."""

from fastapi import FastAPI, HTTPException

from askdata.app.queryservice import QueryService
from askdata.core.errors import AppError, DataError, ModelError, SqlError
from askdata.schemas.query import ErrorInfo, QueryRequest, QueryResponse

_ERROR_STATUS = {DataError: 400, SqlError: 422, ModelError: 502, AppError: 500}


def RegisterQueryRoutes(app: FastAPI, queryService: QueryService, sessionStore):
    """Registers query execution and session reset routes."""

    @app.post("/api/query")
    def Query(request: QueryRequest):
        try:
            return queryService.RunQuery(request)
        except AppError as error:
            status = _ERROR_STATUS.get(type(error), 500)
            raise HTTPException(status_code=status, detail={"code": error.__class__.__name__, "message": str(error)})

    @app.post("/api/sessions/{sessionId}/reset")
    def ResetSession(sessionId: str):
        sessionStore.Reset(sessionId)
        return {"ok": True}
