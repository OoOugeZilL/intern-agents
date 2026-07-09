"""Builds a lightweight searchable schema index for Spider 2.0 databases."""

import re

from askdata.core.errors import DataError
from askdata.schemas.semantic import MatchedColumn, MatchedJoin, MatchedTable, SemanticContext


class SchemaIndex:
    """Indexes Spider schemas and retrieves compact schema context for one question."""

    def __init__(self):
        self.databases = {}

    def Build(self, databases):
        """Stores normalized Spider databases by databaseId for retrieval."""
        self.databases = {database.databaseId: database for database in databases}
        return self

    def Retrieve(self, databaseId, question):
        """Returns matched tables, columns, joins, and a compact schema prompt."""
        database = self.databases.get(databaseId)
        if not database: raise DataError(f"Unknown Spider databaseId: {databaseId}")
        tokens = set(re.findall(r"[a-zA-Z0-9]+", question.lower()))
        matchedTables, matchedColumns = [], []
        for table in database.tables:
            tableHit = self.HasTokenHit(table.tableName, tokens)
            if tableHit: matchedTables.append(MatchedTable(tableName=table.tableName, reason="table name matched"))
            for column in table.columns:
                columnHit = self.HasTokenHit(column.columnName, tokens)
                if tableHit or columnHit: matchedColumns.append(MatchedColumn(tableName=table.tableName, columnName=column.columnName, columnType=column.columnType, reason="name matched"))
        if not matchedTables and database.tables:
            matchedTables = [MatchedTable(tableName=database.tables[0].tableName, reason="fallback first table")]
            matchedColumns = [MatchedColumn(tableName=database.tables[0].tableName, columnName=column.columnName, columnType=column.columnType, reason="fallback first table") for column in database.tables[0].columns]
        tableNames = {table.tableName for table in matchedTables} | {column.tableName for column in matchedColumns}
        joins = [MatchedJoin(**join) for join in database.foreignKeys if join["leftTable"] in tableNames or join["rightTable"] in tableNames]
        schemaPrompt = self.BuildSchemaPrompt(database.databaseId, database.tables, tableNames, joins)
        return SemanticContext(databaseId=database.databaseId, matchedTables=matchedTables, matchedColumns=matchedColumns, matchedJoins=joins, schemaPrompt=schemaPrompt)

    def HasTokenHit(self, name, tokens):
        nameTokens = set(re.findall(r"[a-zA-Z0-9]+", name.lower()))
        return bool(nameTokens & tokens)

    def BuildSchemaPrompt(self, databaseId, tables, tableNames, joins):
        lines = [f"Database: {databaseId}"]
        for table in tables:
            if table.tableName not in tableNames: continue
            columns = ", ".join([f"{column.columnName}:{column.columnType}" for column in table.columns])
            lines.append(f"Table {table.tableName}({columns})")
        for join in joins:
            lines.append(f"Join {join.leftTable}.{join.leftColumn} = {join.rightTable}.{join.rightColumn}")
        return "\n".join(lines)
