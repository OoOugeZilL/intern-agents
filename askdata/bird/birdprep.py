"""Prepares BIRD raw files into compact processed files for the backend."""

from pathlib import Path
import json

from askdata.bird.birdloader import BirdLoader
from askdata.core.errors import DataError
from askdata.schemas.bird import BirdPrepareResult


class BirdPrep:
    """Prepares raw BIRD Mini-Dev SQLite files into processed backend files."""

    def __init__(self, loader=None):
        self.loader = loader or BirdLoader()

    def Prepare(self, rawDir, outDir, demoDir, force=False, split="mini_dev_sqlite"):
        """Reads BIRD files and writes processed database, question, and demo files."""
        rawPath = Path(rawDir)
        if not rawPath.exists(): raise DataError(f"BIRD raw directory does not exist: {rawPath}")
        outPath = Path(outDir)
        demoPath = Path(demoDir)
        targets = [outPath / "databases.json", outPath / "questions.json", outPath / "goldsql.json", demoPath / "demoquestions.json"]
        existing = [str(path) for path in targets if path.exists()]
        if existing and not force: raise DataError(f"Output already exists. Pass --force to overwrite: {', '.join(existing)}")
        databases = self.loader.LoadSchemas(rawPath, split)
        questions = self.loader.LoadQuestions(rawPath, split)
        if not questions: raise DataError("No BIRD questions found")
        outPath.mkdir(parents=True, exist_ok=True)
        demoPath.mkdir(parents=True, exist_ok=True)
        demoQuestions = self.SelectDemoQuestions(questions, 50)
        (outPath / "databases.json").write_text(json.dumps([item.model_dump() for item in databases], ensure_ascii=False, indent=2), encoding="utf-8")
        (outPath / "questions.json").write_text(json.dumps([item.model_dump() for item in questions], ensure_ascii=False, indent=2), encoding="utf-8")
        (outPath / "goldsql.json").write_text(json.dumps([{"questionId": item.questionId, "databaseId": item.databaseId, "goldSql": item.goldSql} for item in questions], ensure_ascii=False, indent=2), encoding="utf-8")
        (demoPath / "demoquestions.json").write_text(json.dumps([item.model_dump() for item in demoQuestions], ensure_ascii=False, indent=2), encoding="utf-8")
        return BirdPrepareResult(databaseCount=len(databases), questionCount=len(questions), demoQuestionCount=len(demoQuestions))

    def SelectDemoQuestions(self, questions, limit):
        selected = []
        usedDatabases = set()
        for question in questions:
            if question.databaseId not in usedDatabases:
                selected.append(question)
                usedDatabases.add(question.databaseId)
            if len(selected) >= limit: return selected
        return (selected + questions)[:limit]
