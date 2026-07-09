"""ReAct agent loop: the LLM reasons, calls tools, and decides when to answer."""

import json
import re

from askdata.agent.llmclient import LlmClient
from askdata.agent.prompts import BuildReActSystemPrompt
from askdata.core.config import LoadSettings
from askdata.core.errors import AppError
from askdata.schemas.query import QueryResponse, TraceStep
from askdata.skills import SkillLoader
from askdata.tools.chartbuilder import ChartBuilder
from askdata.tools.resultanalyzer import ResultAnalyzer
from askdata.tools.sqlexecutor import SqlExecutor
from askdata.tools.sqlvalidator import SqlValidator

RUN_QUERY_TOOL = {
    "type": "function",
    "function": {
        "name": "run_query",
        "description": "Execute a SELECT query against the database. The query is auto-validated (rejects non-SELECT, SELECT *, multi-statement). A LIMIT is added if missing (max 100 rows). Returns column names and a sample of up to 20 result rows. On error, returns the error message so you can fix and retry.",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "The SELECT query to execute.",
                }
            },
            "required": ["sql"],
        },
    },
}

MAX_ITERATIONS = 8


class ReActAgent:
    """Runs a ReAct loop where the LLM reasons, calls tools, and decides when to answer."""

    def __init__(self, llmClient=None, validator=None, executor=None, analyzer=None, chartBuilder=None, settings=None, skillLoader=None):
        self.settings = settings or LoadSettings()
        self.llmClient = llmClient or LlmClient(self.settings)
        self.validator = validator or SqlValidator()
        self.executor = executor or SqlExecutor()
        self.analyzer = analyzer or ResultAnalyzer()
        self.chartBuilder = chartBuilder or ChartBuilder()
        self.skillLoader = skillLoader or SkillLoader()

    def Run(self, request, semanticContext, sessionContext=None):
        """Runs the ReAct loop: the LLM calls run_query until it produces a final answer."""
        trace = [TraceStep(step="RetrieveSchema", status="success", message="Schema matched.")]
        lastSql = ""
        lastColumns = []
        lastRows = []
        executed = False
        answer = ""

        messages = self.BuildInitialMessages(request.question, semanticContext, sessionContext)

        for iteration in range(MAX_ITERATIONS):
            msg = self.llmClient.Chat(messages, tools=[RUN_QUERY_TOOL])

            if msg.content:
                trace.append(TraceStep(step=f"Reason-{iteration + 1}", status="success", message=msg.content[:300]))

            if not msg.tool_calls:
                answer = self.CleanFinalAnswer(msg.content or "No answer produced.")
                break

            if msg.content:
                assistantMsg = {"role": "assistant", "content": msg.content, "tool_calls": self.SerializeToolCalls(msg)}
            else:
                assistantMsg = {"role": "assistant", "content": None, "tool_calls": self.SerializeToolCalls(msg)}
            messages.append(assistantMsg)

            for tc in msg.tool_calls:
                if tc.function.name != "run_query":
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": f"Unknown tool: {tc.function.name}"})
                    continue

                sql = self.ParseSql(tc.function.arguments)
                trace.append(TraceStep(step="GenerateSql", status="success", message=sql[:300]))

                sql = self.CleanSql(sql)

                validation = self.validator.Validate(sql, semanticContext)
                if not validation.valid:
                    trace.append(TraceStep(step="ValidateSql", status="retry", message=validation.message))
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": f"Error: {validation.message}"})
                    continue

                trace.append(TraceStep(step="ValidateSql", status="success", message="SQL validated."))
                lastSql = validation.sql

                databaseUrl = self.BuildDatabaseUrl(semanticContext)
                try:
                    execution = self.executor.Execute(validation.sql, databaseUrl)
                    lastColumns = execution.columns
                    lastRows = execution.rows
                    executed = True
                    trace.append(TraceStep(step="ExecuteSql", status="success", message=f"Returned {len(execution.rows)} rows."))
                    resultText = json.dumps({"columns": execution.columns, "rowCount": len(execution.rows), "rows": execution.rows[:20]}, ensure_ascii=False)
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": resultText})
                except AppError as error:
                    trace.append(TraceStep(step="ExecuteSql", status="retry", message=str(error)))
                    messages.append({"role": "tool", "tool_call_id": tc.id, "content": f"Error: {error}"})
        else:
            if executed:
                answer = self.BuildFallbackAnswer(lastColumns, lastRows)
                trace.append(TraceStep(step="FinalizeAnswer", status="fallback", message="Model did not finalize after successful SQL execution."))
            else:
                answer = "Unable to answer the question within the available steps."

        analysis = self.analyzer.Analyze(request.question, lastColumns, lastRows)
        chart = self.chartBuilder.Build(request.question, lastColumns, lastRows)

        return QueryResponse(
            question=request.question,
            databaseId=request.databaseId,
            answer=answer,
            sql=lastSql or None,
            executionStatus="executed" if executed else "notExecuted",
            columns=lastColumns,
            rows=lastRows,
            chart=chart,
            analysis=analysis,
            trace=trace,
        )

    def BuildInitialMessages(self, question, semanticContext, sessionContext):
        previous = ""
        if sessionContext:
            prevQuestion = sessionContext.get("lastQuestion", "")
            prevSql = sessionContext.get("lastSql", "")
            if prevQuestion and prevSql:
                previous = f"\nPrevious question: {prevQuestion}\nPrevious SQL: {prevSql}"

        systemPrompt = BuildReActSystemPrompt()
        skillsSection = self.skillLoader.BuildPromptSection()
        if skillsSection:
            systemPrompt += "\n\n" + skillsSection

        userContent = f"Question: {question}{previous}\n\nDatabase Schema:\n{semanticContext.schemaPrompt}"

        return [
            {"role": "system", "content": systemPrompt},
            {"role": "user", "content": userContent},
        ]

    def ParseSql(self, arguments):
        try:
            return json.loads(arguments).get("sql", "")
        except json.JSONDecodeError:
            return ""

    def CleanSql(self, text):
        cleaned = text.strip().strip("`")
        if cleaned.lower().startswith("sql"):
            cleaned = cleaned[3:].strip()
        return cleaned

    def SerializeToolCalls(self, msg):
        return [{"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}} for tc in msg.tool_calls]

    def CleanFinalAnswer(self, answer):
        cleaned = (answer or "").strip()
        answerMatch = re.search(r"(?:\*\*)?answer\s*:(?:\*\*)?\s*(.+)\Z", cleaned, re.I | re.S)
        if answerMatch:
            return answerMatch.group(1).strip()
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", cleaned) if paragraph.strip()]
        if paragraphs and re.match(r"(?i)^(yes|no)\b", paragraphs[-1]):
            return paragraphs[-1]
        paragraphs = [paragraph for paragraph in paragraphs if not re.search(r"(?i)\bthe question asks\b", paragraph)]
        if paragraphs:
            cleaned = "\n\n".join(paragraphs)
        cleaned = re.sub(r"(?is)^the question asks:.*?\n\s*\n", "", cleaned).strip()
        cleaned = re.sub(r"(?is)^the answer is .*?\n\s*\n", "", cleaned).strip()
        return cleaned

    def BuildFallbackAnswer(self, columns, rows):
        if not rows:
            return "The query returned no rows."
        shownRows = rows[:5]
        formattedRows = []
        for row in shownRows:
            values = []
            for column in columns:
                value = row.get(column)
                values.append(f"{column}: {value if value is not None else 'NULL'}")
            formattedRows.append("; ".join(values))
        prefix = f"The query returned {len(rows)} row{'s' if len(rows) != 1 else ''}."
        if len(rows) > len(shownRows):
            return f"{prefix} First {len(shownRows)}: " + " | ".join(formattedRows)
        return f"{prefix} " + " | ".join(formattedRows)

    def BuildDatabaseUrl(self, semanticContext):
        if semanticContext.databasePath:
            return f"sqlite:///{semanticContext.databasePath}"
        if self.settings.databaseUrl:
            return self.settings.databaseUrl
        raise AppError(f"No SQLite database path found for databaseId: {semanticContext.databaseId}")
