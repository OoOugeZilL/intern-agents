"""Provides the stable backend service interface used by API routes."""

from askdata.agent.react_agent import ReActAgent
from askdata.bird.birdloader import BirdLoader
from askdata.bird.schemaindex import BirdSchemaIndex
from askdata.core.config import LoadSettings
from askdata.db.mysql_loader import MySQLLoader


class QueryService:
    """Coordinates schema retrieval, agent execution, and session updates."""

    def __init__(self, sessionStore, settings=None, loader=None, agent=None):
        self.settings = settings or LoadSettings()
        self.sessionStore = sessionStore
        self.loader = loader or BirdLoader()
        self.agent = agent or ReActAgent(settings=self.settings)
        self.schemaIndex = None
        self._mysqlLoader = None

    def EnsureSchemaIndex(self):
        """Builds the schema index from BIRD processed data or live MySQL schema."""
        if self.schemaIndex:
            return self.schemaIndex

        if self.settings.useMysql and self.settings.mysqlHost:
            self._mysqlLoader = MySQLLoader(
                host=self.settings.mysqlHost, port=self.settings.mysqlPort,
                user=self.settings.mysqlUser, password=self.settings.mysqlPassword,
                database=self.settings.mysqlDatabase,
            )
            db = self._mysqlLoader.LoadSchema()
            self.schemaIndex = BirdSchemaIndex().Build(
                [db], questions=[], instructionsDir=self.settings.birdInstructionsDir,
            )
        else:
            databases = self.loader.LoadProcessedDatabases(self.settings.birdProcessedDir)
            questions = self.loader.LoadProcessedQuestions(self.settings.birdProcessedDir)
            self.schemaIndex = BirdSchemaIndex().Build(
                databases, questions, instructionsDir=self.settings.birdInstructionsDir,
            )
        return self.schemaIndex

    def RunQuery(self, request):
        """Runs one natural-language data question and returns a stable API response."""
        self.EnsureSchemaIndex()

        if self.settings.useMysql and not request.databaseId:
            request.databaseId = self.settings.mysqlDatabase

        sessionContext = self.sessionStore.Get(request.sessionId)
        semanticContext = self.schemaIndex.Retrieve(request.databaseId, request.question)
        response = self.agent.Run(request, semanticContext, sessionContext)
        if not request.showSql:
            response.sql = None
        if not request.showTrace:
            response.trace = []
        self.sessionStore.Save(request.sessionId, {
            "lastQuestion": request.question, "lastSql": response.sql,
            "lastDatabaseId": request.databaseId, "lastColumns": response.columns,
        })
        return response
