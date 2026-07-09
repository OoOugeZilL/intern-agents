"""Loads raw and processed Spider 2.0 files into normalized schema objects."""

import json
from pathlib import Path

from askdata.core.errors import DataError
from askdata.schemas.spider import SpiderColumn, SpiderDatabase, SpiderQuestion, SpiderTable


class SpiderLoader:
    """Loads Spider 2.0 raw or processed files into normalized objects."""

    def LoadSchemas(self, rawDir):
        """Reads raw tables.json and returns normalized SpiderDatabase objects."""
        rawPath = Path(rawDir)
        tablesPath = rawPath / "tables.json"
        if not tablesPath.exists(): raise DataError(f"Missing Spider schema file: {tablesPath}")
        try:
            items = json.loads(tablesPath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise DataError(f"Invalid JSON in {tablesPath}: {error}") from error
        databases = []
        for item in items:
            databaseId = item.get("db_id") or item.get("database_id") or item.get("databaseId")
            if not databaseId: raise DataError("Spider schema item is missing database id")
            tableNames = item.get("table_names_original") or item.get("table_names") or []
            columnItems = item.get("column_names_original") or item.get("column_names") or []
            columnTypes = item.get("column_types") or []
            primaryIndexes = set(item.get("primary_keys") or [])
            tableMap = {tableName: [] for tableName in tableNames}
            for index, columnItem in enumerate(columnItems):
                if not isinstance(columnItem, list) or len(columnItem) < 2: continue
                tableIndex, columnName = columnItem[0], columnItem[1]
                if tableIndex < 0 or columnName == "*": continue
                tableName = tableNames[tableIndex]
                columnType = columnTypes[index] if index < len(columnTypes) else "text"
                tableMap[tableName].append(SpiderColumn(tableName=tableName, columnName=columnName, columnType=columnType, isPrimary=index in primaryIndexes))
            tables = [SpiderTable(tableName=tableName, columns=columns) for tableName, columns in tableMap.items()]
            foreignKeys = self.BuildForeignKeys(item.get("foreign_keys") or [], columnItems, tableNames)
            primaryKeys = [self.ColumnRef(index, columnItems, tableNames) for index in primaryIndexes if self.ColumnRef(index, columnItems, tableNames)]
            databases.append(SpiderDatabase(databaseId=databaseId, tables=tables, primaryKeys=primaryKeys, foreignKeys=foreignKeys))
        return databases

    def LoadQuestions(self, rawDir, split):
        """Reads raw question files for a split and returns normalized SpiderQuestion objects."""
        rawPath = Path(rawDir)
        paths = [rawPath / f"{split}.json", rawPath / f"{split}_spider.json", rawPath / f"{split}_others.json"]
        items = []
        for path in paths:
            if path.exists():
                try:
                    loaded = json.loads(path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as error:
                    raise DataError(f"Invalid JSON in {path}: {error}") from error
                items.extend(loaded if isinstance(loaded, list) else loaded.get("data", []))
        if not items: raise DataError(f"No Spider question file found for split '{split}' in {rawPath}")
        questions = []
        for index, item in enumerate(items):
            databaseId = item.get("db_id") or item.get("database_id") or item.get("databaseId")
            question = item.get("question") or item.get("utterance") or ""
            goldSql = item.get("query") or item.get("sql") or item.get("goldSql") or ""
            if databaseId and question: questions.append(SpiderQuestion(questionId=str(item.get("question_id") or item.get("questionId") or f"{split}{index:05d}"), databaseId=databaseId, question=question, goldSql=goldSql, split=split))
        return questions

    def LoadProcessedDatabases(self, processedDir):
        """Reads processed/databases.json and returns normalized SpiderDatabase objects."""
        path = Path(processedDir) / "databases.json"
        if not path.exists(): raise DataError(f"Missing processed databases file: {path}")
        try:
            return [SpiderDatabase.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]
        except json.JSONDecodeError as error:
            raise DataError(f"Invalid JSON in {path}: {error}") from error

    def LoadProcessedQuestions(self, processedDir):
        """Reads processed/questions.json and returns normalized SpiderQuestion objects."""
        path = Path(processedDir) / "questions.json"
        if not path.exists(): raise DataError(f"Missing processed questions file: {path}")
        try:
            return [SpiderQuestion.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]
        except json.JSONDecodeError as error:
            raise DataError(f"Invalid JSON in {path}: {error}") from error

    def ColumnRef(self, index, columnItems, tableNames):
        if index < 0 or index >= len(columnItems): return None
        tableIndex, columnName = columnItems[index][0], columnItems[index][1]
        if tableIndex < 0: return None
        return {"tableName": tableNames[tableIndex], "columnName": columnName}

    def BuildForeignKeys(self, rawKeys, columnItems, tableNames):
        foreignKeys = []
        for leftIndex, rightIndex in rawKeys:
            left = self.ColumnRef(leftIndex, columnItems, tableNames)
            right = self.ColumnRef(rightIndex, columnItems, tableNames)
            if left and right: foreignKeys.append({"leftTable": left["tableName"], "leftColumn": left["columnName"], "rightTable": right["tableName"], "rightColumn": right["columnName"]})
        return foreignKeys
