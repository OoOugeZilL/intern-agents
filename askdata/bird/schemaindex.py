"""Builds a lightweight searchable schema index for BIRD databases."""

import re
from pathlib import Path

from askdata.core.errors import DataError
from askdata.schemas.semantic import MatchedColumn, MatchedJoin, MatchedTable, SemanticContext


class BirdSchemaIndex:
    """Indexes BIRD schemas and retrieves compact schema context for one question."""

    def __init__(self):
        self.databases = {}
        self.questions = []
        self.instructionsDir = None

    def Build(self, databases, questions=None, instructionsDir=None):
        """Stores normalized BIRD databases and questions for retrieval."""
        self.databases = {database.databaseId: database for database in databases}
        self.questions = questions or []
        self.instructionsDir = Path(instructionsDir) if instructionsDir else None
        return self

    def Retrieve(self, databaseId, question):
        """Retrieves a compact schema context for one BIRD database and question."""
        database = self.databases.get(databaseId)
        if not database: raise DataError(f"Unknown BIRD databaseId: {databaseId}")
        tokens = set(re.findall(r"[A-Za-z0-9]+", question.lower()))
        matchedTables = []
        matchedColumns = []
        for table in database.tables:
            tableTokens = set(re.findall(r"[A-Za-z0-9]+", table.tableName.lower()))
            tableMatched = bool(tokens & tableTokens)
            columnMatches = []
            for column in table.columns:
                columnTokens = set(re.findall(r"[A-Za-z0-9]+", column.columnName.lower()))
                if tokens & columnTokens:
                    columnMatches.append(column)
                    matchedColumns.append(MatchedColumn(tableName=table.tableName, columnName=column.columnName, columnType=column.columnType, reason="Token match."))
            if tableMatched or columnMatches:
                matchedTables.append(MatchedTable(tableName=table.tableName, reason="Token match."))
        if not matchedTables: matchedTables = [MatchedTable(tableName=table.tableName, reason="Included for compact database context.") for table in database.tables[:8]]
        selectedNames = {table.tableName for table in matchedTables}
        for table in database.tables:
            if table.tableName in selectedNames:
                for column in table.columns:
                    if column.isPrimary and not any(item.tableName == table.tableName and item.columnName == column.columnName for item in matchedColumns):
                        matchedColumns.append(MatchedColumn(tableName=table.tableName, columnName=column.columnName, columnType=column.columnType, reason="Primary key."))
        matchedJoins = [MatchedJoin(leftTable=item["leftTable"], leftColumn=item["leftColumn"], rightTable=item["rightTable"], rightColumn=item["rightColumn"]) for item in database.foreignKeys if item.get("leftTable") in selectedNames or item.get("rightTable") in selectedNames]
        evidence = self.FindEvidence(databaseId, question)
        schemaPrompt = self.BuildSchemaPrompt(database, selectedNames, evidence)
        return SemanticContext(databaseId=databaseId, databasePath=database.databasePath or None, matchedTables=matchedTables, matchedColumns=matchedColumns, matchedJoins=matchedJoins, schemaPrompt=schemaPrompt)

    def _LoadInstructions(self, databaseId):
        if not self.instructionsDir:
            return None
        path = self.instructionsDir / f"{databaseId}.md"
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        businessSection = self._ExtractBusinessMappings(content)
        joinSection = self._ExtractJoinPatterns(content)
        parts = []
        if businessSection:
            parts.append(f"Term mappings:\n{businessSection}")
        if joinSection:
            parts.append(f"JOIN patterns:\n{joinSection}")
        return "\n\n".join(parts) if parts else None

    def _ExtractBusinessMappings(self, content):
        inSection = False
        mappings = []
        for line in content.split("\n"):
            if "Business Term Mappings" in line:
                inSection = True
                continue
            if inSection:
                if line.strip().startswith("<!--"):
                    break
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith("```") and not stripped.startswith("_Add"):
                    mappings.append(stripped)
        return "\n".join(mappings) if mappings else None

    def _ExtractJoinPatterns(self, content):
        inSection = False
        joins = []
        for line in content.split("\n"):
            if "JOIN Patterns" in line:
                inSection = True
                continue
            if inSection:
                if line.strip().startswith("##") or line.strip().startswith("#"):
                    break
                stripped = line.strip()
                if stripped and stripped.startswith("-"):
                    joins.append(stripped)
        return "\n".join(joins) if joins else None

    def FindEvidence(self, databaseId, question):
        """Finds BIRD evidence text for the matching dev question when available."""
        normalized = question.strip().lower()
        for item in self.questions:
            if item.databaseId == databaseId and item.question.strip().lower() == normalized:
                return item.evidence
        return None

    def BuildSchemaPrompt(self, database, selectedNames, evidence):
        lines = [f"Database: {database.databaseId}", "Dialect: SQLite"]
        if database.databasePath: lines.append(f"SQLite path: {database.databasePath}")
        if evidence: lines.append(f"Evidence: {evidence}")

        instructions = self._LoadInstructions(database.databaseId)
        if instructions:
            lines.append(f"\n--- Business Context ---\n{instructions}\n---")

        for table in database.tables:
            if selectedNames and table.tableName not in selectedNames and len(selectedNames) < len(database.tables) and len(database.tables) > 8: continue
            columns = ", ".join([f"{column.columnName} {column.columnType}".strip() for column in table.columns])
            lines.append(f"Table {table.tableName}({columns})")
        for key in database.foreignKeys:
            if key.get("leftTable") in selectedNames or key.get("rightTable") in selectedNames:
                lines.append(f"Join {key.get('leftTable')}.{key.get('leftColumn')} = {key.get('rightTable')}.{key.get('rightColumn')}")
        return "\n".join(lines)
