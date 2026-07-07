"""Loads raw and processed BIRD files into normalized schema objects."""

from pathlib import Path
import json
import sqlite3

from askdata.core.errors import DataError
from askdata.schemas.bird import BirdColumn, BirdDatabase, BirdQuestion, BirdTable


QUESTION_FILES = ["mini_dev_sqlite.json", "dev.json"]


class BirdLoader:
    """Loads BIRD Mini-Dev or Full Dev SQLite files into normalized objects."""

    def LoadSchemas(self, rawDir, split="mini_dev_sqlite"):
        """Reads BIRD sqlite databases and returns BirdDatabase objects."""
        root = self.FindBirdRoot(rawDir, split)
        questions = self.LoadQuestions(rawDir, split)
        databaseIds = sorted({question.databaseId for question in questions})
        return [self.LoadDatabase(root, databaseId) for databaseId in databaseIds]

    def LoadQuestions(self, rawDir, split="mini_dev_sqlite"):
        """Reads the BIRD question JSON and returns normalized BirdQuestion objects."""
        root = self.FindBirdRoot(rawDir, split)
        questionFile = f"{split}.json"
        path = root / questionFile
        if not path.exists(): raise DataError(f"Missing BIRD question file: {path}")
        try:
            items = json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:
            raise DataError(f"Invalid BIRD question JSON: {path}") from error
        questions = []
        for index, item in enumerate(items):
            databaseId = item.get("db_id") or item.get("databaseId")
            question = item.get("question")
            if databaseId and question:
                questions.append(BirdQuestion(
                    questionId=str(item.get("question_id") or item.get("questionId") or f"bird{index:05d}"),
                    databaseId=databaseId,
                    question=question,
                    evidence=item.get("evidence"),
                    goldSql=item.get("SQL") or item.get("sql"),
                    difficulty=item.get("difficulty"),
                    split=split))
        if not questions: raise DataError(f"No BIRD questions found in {path}")
        return questions

    def LoadProcessedDatabases(self, processedDir):
        """Reads processed/databases.json and returns normalized BirdDatabase objects."""
        path = Path(processedDir) / "databases.json"
        if not path.exists(): raise DataError(f"Missing processed BIRD databases file: {path}")
        try:
            return [BirdDatabase.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]
        except Exception as error:
            raise DataError(f"Invalid processed BIRD databases file: {path}") from error

    def LoadProcessedQuestions(self, processedDir):
        """Reads processed/questions.json and returns normalized BirdQuestion objects."""
        path = Path(processedDir) / "questions.json"
        if not path.exists(): raise DataError(f"Missing processed BIRD questions file: {path}")
        try:
            return [BirdQuestion.model_validate(item) for item in json.loads(path.read_text(encoding="utf-8"))]
        except Exception as error:
            raise DataError(f"Invalid processed BIRD questions file: {path}") from error

    def FindBirdRoot(self, rawDir, split="mini_dev_sqlite"):
        """Finds the folder containing the BIRD question JSON file."""
        rawPath = Path(rawDir)
        if not rawPath.exists(): raise DataError(f"BIRD raw directory does not exist: {rawPath}")
        questionFile = f"{split}.json"
        candidates = [
            rawPath / "mini_dev" / "mini_dev_data",
            rawPath / "mini_dev_data",
            rawPath / "bird_mini_dev" / "mini_dev_data",
            rawPath,
        ]
        for candidate in candidates:
            if (candidate / questionFile).exists(): return candidate
        matches = list(rawPath.rglob(questionFile))
        if matches: return matches[0].parent
        raise DataError(f"Missing BIRD {questionFile} under {rawPath}")

    def LoadDatabase(self, root, databaseId):
        """Inspects one BIRD sqlite database and returns its normalized schema."""
        databasePath = self.FindDatabasePath(root, databaseId)
        if not databasePath: return BirdDatabase(databaseId=databaseId)
        try:
            connection = sqlite3.connect(databasePath)
            try:
                tableNames = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
                tables = [self.LoadTable(connection, tableName) for tableName in tableNames]
                foreignKeys = self.LoadForeignKeys(connection, tableNames)
                primaryKeys = [{"tableName": column.tableName, "columnName": column.columnName} for table in tables for column in table.columns if column.isPrimary]
                return BirdDatabase(databaseId=databaseId, databasePath=str(databasePath), tables=tables, primaryKeys=primaryKeys, foreignKeys=foreignKeys)
            finally:
                connection.close()
        except Exception as error:
            raise DataError(f"Failed to inspect BIRD sqlite database {databasePath}: {error}") from error

    def LoadTable(self, connection, tableName):
        rows = connection.execute(f"PRAGMA table_info({self.QuoteName(tableName)})").fetchall()
        columns = [BirdColumn(tableName=tableName, columnName=row[1], columnType=row[2] or "text", isPrimary=bool(row[5])) for row in rows]
        return BirdTable(tableName=tableName, columns=columns)

    def LoadForeignKeys(self, connection, tableNames):
        keys = []
        for tableName in tableNames:
            for row in connection.execute(f"PRAGMA foreign_key_list({self.QuoteName(tableName)})").fetchall():
                rightTable = row[2]
                leftColumn = row[3]
                rightColumn = row[4]
                if rightTable and leftColumn and rightColumn:
                    keys.append({"leftTable": tableName, "leftColumn": leftColumn, "rightTable": rightTable, "rightColumn": rightColumn})
        return keys

    def FindDatabasePath(self, root, databaseId):
        bases = [Path(root) / "dev_databases" / databaseId]
        if not (Path(root) / "dev_databases").exists():
            bases.append(Path(root) / "mini_dev_data" / "dev_databases" / databaseId)
            bases.append(Path(root) / "minidev" / "MINIDEV" / "dev_databases" / databaseId)
        for base in bases:
            candidates = [base / "sqlite" / f"{databaseId}.sqlite", base / f"{databaseId}.sqlite", base / "sqlite" / f"{databaseId}.db", base / f"{databaseId}.db"]
            for path in candidates:
                if path.exists(): return path
            matches = list(base.rglob("*.sqlite")) + list(base.rglob("*.db"))
            if matches: return matches[0]
        return None

    def QuoteName(self, name):
        return '"' + name.replace('"', '""') + '"'
