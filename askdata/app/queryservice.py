"""Provides the stable backend service interface used by API routes."""

from askdata.agent.react_agent import ReActAgent
from askdata.bird.birdloader import BirdLoader
from askdata.bird.schemaindex import BirdSchemaIndex
from askdata.core.config import LoadSettings


class QueryService:
    """Coordinates schema retrieval, agent execution, and session updates."""

    def __init__(self, sessionStore, settings=None, loader=None, agent=None):
        self.settings = settings or LoadSettings()
        self.sessionStore = sessionStore
        self.loader = loader or BirdLoader()
        self.agent = agent or ReActAgent(settings=self.settings)
        self.schemaIndex = None

    def EnsureSchemaIndex(self):
        """Builds the schema index from processed data. Safe to call multiple times."""
        if not self.schemaIndex:
            databases = self.loader.LoadProcessedDatabases(self.settings.birdProcessedDir)
            questions = self.loader.LoadProcessedQuestions(self.settings.birdProcessedDir)
            self.schemaIndex = BirdSchemaIndex().Build(databases, questions, instructionsDir=self.settings.birdInstructionsDir)
        return self.schemaIndex

    def RunQuery(self, request):
        """Runs one natural-language data question and returns a stable API response."""
        self.EnsureSchemaIndex()
        sessionContext = self.sessionStore.Get(request.sessionId)
        semanticContext = self.schemaIndex.Retrieve(request.databaseId, request.question)
        response = self.agent.Run(request, semanticContext, sessionContext)
        self.sessionStore.Save(request.sessionId, {"lastQuestion": request.question, "lastSql": response.sql, "lastDatabaseId": request.databaseId, "lastColumns": response.columns})
        return response
