"""Coordinates the controlled agent flow from SQL generation to final answer."""

from askdata.agent.llmclient import LlmClient
from askdata.agent.prompts import BuildAnswerPrompt, BuildRepairPrompt, BuildSqlPrompt
from askdata.core.config import LoadSettings
from askdata.core.errors import AppError
from askdata.schemas.query import QueryResponse, TraceStep
from askdata.tools.chartbuilder import ChartBuilder
from askdata.tools.resultanalyzer import ResultAnalyzer
from askdata.tools.sqlexecutor import SqlExecutor
from askdata.tools.sqlvalidator import SqlValidator


class AgentGraph:
    """Runs the controlled V1 agent flow without exposing internal steps to API routes."""

    def __init__(self, llmClient=None, validator=None, executor=None, analyzer=None, chartBuilder=None, settings=None):
        self.settings = settings or LoadSettings()
        self.llmClient = llmClient or LlmClient(self.settings)
        self.validator = validator or SqlValidator()
        self.executor = executor or SqlExecutor()
        self.analyzer = analyzer or ResultAnalyzer()
        self.chartBuilder = chartBuilder or ChartBuilder()

    def Run(self, request, semanticContext, sessionContext=None):
        """Generates, validates, executes, analyzes, and answers one query."""
        trace = [TraceStep(step="RetrieveSchema", status="success", message="Schema matched.")]
        sql = self.CleanSql(self.llmClient.Complete(BuildSqlPrompt(request.question, semanticContext, sessionContext or {})))
        validation = self.validator.Validate(sql, semanticContext)
        if not validation.valid:
            trace.append(TraceStep(step="ValidateSql", status="retry", message=validation.message))
            sql = self.CleanSql(self.llmClient.Complete(BuildRepairPrompt(request.question, sql, validation.message, semanticContext)))
            validation = self.validator.Validate(sql, semanticContext)
        if not validation.valid: raise AppError(validation.message)
        trace.append(TraceStep(step="ValidateSql", status="success", message="SQL validated."))
        databaseUrl = self.BuildDatabaseUrl(semanticContext)
        try:
            execution = self.executor.Execute(validation.sql, databaseUrl)
        except AppError as error:
            trace.append(TraceStep(step="ExecuteSql", status="retry", message=str(error)))
            sql = self.CleanSql(self.llmClient.Complete(BuildRepairPrompt(request.question, validation.sql, str(error), semanticContext)))
            validation = self.validator.Validate(sql, semanticContext)
            if not validation.valid: raise AppError(validation.message)
            execution = self.executor.Execute(validation.sql, databaseUrl)
        trace.append(TraceStep(step="ExecuteSql", status="success", message=f"Returned {len(execution.rows)} rows."))
        analysis = self.analyzer.Analyze(request.question, execution.columns, execution.rows)
        chart = self.chartBuilder.Build(request.question, execution.columns, execution.rows)
        answer = self.BuildAnswer(request, validation.sql, execution.columns, execution.rows, analysis)
        return QueryResponse(question=request.question, databaseId=request.databaseId, answer=answer, sql=validation.sql, executionStatus="executed", columns=execution.columns, rows=execution.rows, chart=chart, analysis=analysis, trace=trace)

    def BuildAnswer(self, request, sql, columns, rows, analysis):
        prompt = BuildAnswerPrompt(request.question, sql, columns, rows)
        try:
            return self.llmClient.Complete(prompt)
        except AppError:
            return analysis["summary"]

    def CleanSql(self, text):
        cleaned = text.strip().strip("`")
        if cleaned.lower().startswith("sql"): cleaned = cleaned[3:].strip()
        return cleaned

    def BuildDatabaseUrl(self, semanticContext):
        """Builds a SQLite URL from the retrieved BIRD database path."""
        if semanticContext.databasePath: return f"sqlite:///{semanticContext.databasePath}"
        if self.settings.databaseUrl: return self.settings.databaseUrl
        raise AppError(f"No SQLite database path found for databaseId: {semanticContext.databaseId}")
