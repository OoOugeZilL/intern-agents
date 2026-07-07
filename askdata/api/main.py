"""Defines the FastAPI app and registers backend routes."""

from fastapi import FastAPI

from askdata.api.birdroutes import RegisterBirdRoutes
from askdata.api.queryroutes import RegisterQueryRoutes
from askdata.app.queryservice import QueryService
from askdata.app.sessionstore import SessionStore
from askdata.core.config import LoadSettings


def CreateApp():
    """Creates the FastAPI app and registers all backend routes."""
    settings = LoadSettings()
    sessionStore = SessionStore()
    queryService = QueryService(sessionStore=sessionStore, settings=settings)
    app = FastAPI(title="AskData Backend")

    @app.get("/health")
    def Health():
        return {"ok": True}

    RegisterQueryRoutes(app, queryService, sessionStore)
    RegisterBirdRoutes(app, settings)
    return app


app = CreateApp()
