"""Prepares Spider 2.0 raw files into compact processed files for the backend."""

import json
from pathlib import Path

from askdata.core.errors import DataError
from askdata.schemas.spider import SpiderPrepareResult
from askdata.spider.spiderloader import SpiderLoader


class SpiderPrep:
    """Prepares raw Spider 2.0 files into processed backend files."""

    def __init__(self, loader=None):
        self.loader = loader or SpiderLoader()

    def Prepare(self, rawDir, outDir, demoDir, force=False):
        """Reads raw Spider files and writes processed database, question, and demo files."""
        rawPath, outPath, demoPath = Path(rawDir), Path(outDir), Path(demoDir)
        if not rawPath.exists(): raise DataError(f"Spider raw directory does not exist: {rawPath}")
        outputFiles = [outPath / "databases.json", outPath / "questions.json", outPath / "goldsql.json", demoPath / "demoquestions.json"]
        existing = [str(path) for path in outputFiles if path.exists()]
        if existing and not force: raise DataError(f"Output files already exist. Pass --force to replace: {', '.join(existing)}")
        databases = self.loader.LoadSchemas(rawPath)
        questions = []
        for split in ["train", "dev"]:
            try:
                questions.extend(self.loader.LoadQuestions(rawPath, split))
            except DataError:
                pass
        if not questions: raise DataError("No Spider questions found for train or dev split")
        outPath.mkdir(parents=True, exist_ok=True)
        demoPath.mkdir(parents=True, exist_ok=True)
        demoQuestions = self.SelectDemoQuestions(questions)
        (outPath / "databases.json").write_text(json.dumps([item.model_dump() for item in databases], ensure_ascii=False, indent=2), encoding="utf-8")
        (outPath / "questions.json").write_text(json.dumps([item.model_dump() for item in questions], ensure_ascii=False, indent=2), encoding="utf-8")
        (outPath / "goldsql.json").write_text(json.dumps([{"questionId": item.questionId, "databaseId": item.databaseId, "goldSql": item.goldSql} for item in questions], ensure_ascii=False, indent=2), encoding="utf-8")
        (demoPath / "demoquestions.json").write_text(json.dumps([item.model_dump() for item in demoQuestions], ensure_ascii=False, indent=2), encoding="utf-8")
        return SpiderPrepareResult(databaseCount=len(databases), questionCount=len(questions), demoQuestionCount=len(demoQuestions))

    def SelectDemoQuestions(self, questions):
        seen, selected = set(), []
        for question in questions:
            if question.databaseId not in seen or len(selected) < 30:
                selected.append(question)
                seen.add(question.databaseId)
            if len(selected) >= 50: break
        return selected
