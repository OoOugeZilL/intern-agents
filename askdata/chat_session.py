"""Interactive CLI chat session with auto-detect database and formatted output."""

import json
import os
import random
import re
import uuid
from pathlib import Path

from askdata.core.config import LoadSettings
from askdata.schemas.query import QueryRequest


class Color:
    """ANSI escape codes for terminal colors."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"


def c(text, *styles):
    """Wrap text in ANSI styles. c('hello', Color.CYAN, Color.BOLD)"""
    prefix = "".join(styles)
    return f"{prefix}{text}{Color.RESET}"


class ChatSession:
    """Runs an interactive REPL for natural-language data questions."""

    def __init__(self, queryService, databaseId=None, settings=None):
        self.queryService = queryService
        self.databaseId = databaseId
        self.sessionId = str(uuid.uuid4())[:8]
        self.settings = settings or LoadSettings()
        self._schemaIndex = None
        self._questions = []
        self._goldByQuestion = {}

    def Start(self):
        """Runs the interactive REPL loop."""
        self._EnsureSchemaIndex()
        self._LoadQuestions()
        self._PrintWelcome()
        while True:
            try:
                line = input(c("\n❯ ", Color.BOLD)).strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n{Color.DIM}Bye.{Color.RESET}")
                break
            if not line:
                continue
            if line.startswith("/"):
                self._HandleCommand(line)
                continue
            self._HandleQuestion(line)

    def _EnsureSchemaIndex(self):
        self._schemaIndex = self.queryService.EnsureSchemaIndex()

    def _LoadQuestions(self):
        processedDir = self.settings.birdProcessedDir
        questionsPath = Path(processedDir) / "questions.json"
        if questionsPath.exists():
            self._questions = json.loads(questionsPath.read_text(encoding="utf-8"))
            for q in self._questions:
                key = (q["databaseId"], q["question"].strip().lower())
                self._goldByQuestion[key] = q.get("goldSql", "")

    def _PrintWelcome(self):
        dbs = list(self._schemaIndex.databases.keys())
        qCount = len(self._questions)
        print(f"\n{c('AskData', Color.BOLD)} chat — {len(dbs)} databases, {qCount} questions loaded.")
        if self.databaseId:
            print(f"Database: {c(self.databaseId, Color.CYAN)}")
        else:
            print("Database: auto-detect")
        print(f"{Color.DIM}Type /examples to explore, /help for commands, /quit to exit.{Color.RESET}")

    def _HandleCommand(self, line):
        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd == "/quit":
            print(f"{Color.DIM}Bye.{Color.RESET}")
            exit(0)
        elif cmd == "/clear":
            os.system("clear")
        elif cmd == "/help":
            self._PrintHelp()
        elif cmd == "/databases":
            self._ListDatabases()
        elif cmd == "/examples":
            self._ShowExamples(arg)
        elif cmd == "/use":
            self._SwitchDatabase(arg)
        elif cmd == "/reset":
            self.sessionId = str(uuid.uuid4())[:8]
            print(f"Session reset. {Color.DIM}New session: {self.sessionId}{Color.RESET}")
        else:
            print(f"Unknown command: {c(cmd, Color.RED)}. Type /help for commands.")

    def _PrintHelp(self):
        print(f"\n{c('Commands', Color.BOLD)}")
        print(f"  {c('/examples', Color.CYAN)} [simple|moderate|challenging|all]  Show sample questions")
        print(f"  {c('/databases', Color.CYAN)}                               List available databases")
        print(f"  {c('/use', Color.CYAN)} <db>                                Switch to a specific database")
        print(f"  {c('/use auto', Color.CYAN)}                               Go back to auto-detection")
        print(f"  {c('/reset', Color.CYAN)}                                   Clear conversation context")
        print(f"  {c('/clear', Color.CYAN)}                                   Clear the terminal screen")
        print(f"  {c('/quit', Color.CYAN)}                                    Exit")

    def _ShowExamples(self, arg):
        difficultyFilter = None
        showAll = False

        if arg == "all":
            showAll = True
        elif arg and arg in ("simple", "moderate", "challenging"):
            difficultyFilter = arg
        elif arg != "":
            print(f"Unknown filter: {c(arg, Color.RED)}. Use: simple, moderate, challenging, or all.")
            return

        candidates = self._questions

        if not showAll and self.databaseId:
            candidates = [q for q in candidates if q.get("databaseId") == self.databaseId]
            dbLabel = f"{Color.DIM} — {self.databaseId}{Color.RESET}"
        else:
            dbLabel = f"{Color.DIM} — all databases{Color.RESET}"

        if difficultyFilter:
            candidates = [q for q in candidates if q.get("difficulty") == difficultyFilter]
            label = f"{difficultyFilter.upper()}{dbLabel}"
        else:
            label = f"All difficulties{dbLabel}"

        if not candidates:
            print(f"\n{c('No examples found', Color.DIM)} for {label}")
            if self.databaseId and not showAll:
                print(f"Try {c('/examples all', Color.CYAN)} to see questions from other databases.")
            return

        print(f"\n{c(f'=== {label} ({len(candidates)} questions) ===', Color.BOLD)}\n")

        sample = random.sample(candidates, min(5, len(candidates)))
        for i, q in enumerate(sample, 1):
            diffColor = {"simple": Color.GREEN, "moderate": Color.YELLOW, "challenging": Color.RED}.get(q["difficulty"], Color.DIM)
            diffLabel = c(f"[{q['difficulty']}]", diffColor)
            dbLabel = c(q["databaseId"], Color.CYAN)
            print(f"  {c(str(i), Color.DIM)}. {diffLabel} {dbLabel}")
            print(f"     {c('Q:', Color.DIM)} {q['question']}")
            if q.get("evidence"):
                print(f"     {c('Hint:', Color.DIM)} {q['evidence'][:150]}")
            print(f"     {c('Gold:', Color.YELLOW)} {q.get('goldSql', '')[:200]}")
            print()

    def _SwitchDatabase(self, arg):
        if arg == "auto":
            self.databaseId = None
            print("Switched to auto-detection.")
        elif arg:
            dbs = self._schemaIndex.databases
            if arg in dbs:
                self.databaseId = arg
                info = dbs[arg]
                tableCount = len(info.tables) if hasattr(info, "tables") else 0
                print(f"Using database: {c(arg, Color.CYAN)} ({tableCount} tables)")
            else:
                print(f"Unknown database: {c(arg, Color.RED)}")
                print(f"Available: {c(', '.join(sorted(dbs.keys())), Color.DIM)}")
        else:
            print(f"Usage: {c('/use <database>', Color.CYAN)} or {c('/use auto', Color.CYAN)}")

    def _ListDatabases(self):
        dbs = self._schemaIndex.databases
        header = f"{'Database':<35} {'Tables':<8} {'Questions':<10}"
        print(f"\n{c(header, Color.BOLD)}")
        print(f"{Color.DIM}{'-' * 55}{Color.RESET}")
        dbQuestionCounts = {}
        for q in self._questions:
            dbId = q.get("databaseId", "")
            dbQuestionCounts[dbId] = dbQuestionCounts.get(dbId, 0) + 1
        for dbId in sorted(dbs.keys()):
            db = dbs[dbId]
            tableCount = len(db.tables) if hasattr(db, "tables") else 0
            qCount = dbQuestionCounts.get(dbId, 0)
            marker = c(" *", Color.CYAN) if dbId == self.databaseId else "  "
            print(f"{marker}{c(dbId, Color.CYAN) if dbId == self.databaseId else dbId:<35} {tableCount:<8} {qCount:<10}")

    def _HandleQuestion(self, question):
        if self.databaseId:
            databaseId = self.databaseId
            bestId, bestScore = self._ScoreBestDatabase(question)
            if bestId and bestId != self.databaseId and bestScore >= 3:
                print(f"\n{c('Note:', Color.YELLOW)} question looks more like {c(bestId, Color.CYAN)} than {c(self.databaseId, Color.DIM)}.")
                print(f"Use {c(f'/use {bestId}', Color.CYAN)} to switch, or re-ask to continue.")
        else:
            databaseId = self._DetectDatabase(question)
            if not databaseId:
                return

        print(f"\n{c('...', Color.DIM)}", end="\r")
        request = QueryRequest(question=question, databaseId=databaseId, sessionId=self.sessionId)
        try:
            response = self.queryService.RunQuery(request)
        except Exception as error:
            print(f"{c('Error:', Color.RED)} {error}")
            return

        goldSql = self._goldByQuestion.get((databaseId, question.strip().lower()), "")
        self._PrintResult(response, databaseId, goldSql)

    def _PrintResult(self, response, databaseId, goldSql=""):
        detectNote = ""
        if not self.databaseId:
            detectNote = f" {Color.DIM}(auto-detected){Color.RESET}"

        print(f"\n{c('database', Color.DIM)}: {c(databaseId, Color.CYAN)}{detectNote}")

        if response.sql:
            print(f"{c('SQL', Color.DIM)}:   {c(response.sql, Color.GRAY)}")

        if goldSql:
            print(f"{c('Gold', Color.DIM)}:  {c(goldSql, Color.YELLOW)}")

        print(f"\n{response.answer}")

        if response.error:
            print(f"\n{c('Error:', Color.RED)} {response.error.message}")

    def _DetectDatabase(self, question):
        dbs = self._schemaIndex.databases
        if len(dbs) == 1:
            return list(dbs.keys())[0]

        bestId, bestScore = self._ScoreBestDatabase(question)
        if bestScore == 0 or bestScore <= 2:
            return self._AskPickDatabase(dbs)

        return bestId

    def _ScoreBestDatabase(self, question):
        """Scores databases against question tokens. Returns (bestDbId, bestScore)."""
        dbs = self._schemaIndex.databases
        tokens = set(re.findall(r"[A-Za-z0-9]+", question.lower()))
        if not tokens:
            return (None, 0)

        scores = {}
        for dbId, db in dbs.items():
            score = 0
            dbTokens = set(re.findall(r"[A-Za-z0-9]+", dbId.lower()))
            score += len(tokens & dbTokens) * 3
            for table in db.tables:
                tableTokens = set(re.findall(r"[A-Za-z0-9]+", table.tableName.lower()))
                score += len(tokens & tableTokens) * 2
                for column in table.columns:
                    colTokens = set(re.findall(r"[A-Za-z0-9]+", column.columnName.lower()))
                    score += len(tokens & colTokens)
            scores[dbId] = score

        sortedScores = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if not sortedScores:
            return (None, 0)
        return sortedScores[0]

    def _AskPickDatabase(self, dbs, top=None):
        dbList = sorted(top) if top else sorted(dbs.keys())
        print(f"\n{c('Which database?', Color.BOLD)}")
        for index, dbId in enumerate(dbList):
            db = dbs[dbId]
            tableCount = len(db.tables) if hasattr(db, "tables") else 0
            qCount = len([q for q in self._questions if q.get("databaseId") == dbId])
            print(f"  {c(str(index + 1), Color.DIM)}. {c(dbId, Color.CYAN)} {Color.DIM}({tableCount} tables, {qCount} questions){Color.RESET}")
        print(f"  {Color.DIM}Type a number, name, or /quit to cancel.{Color.RESET}")
        while True:
            try:
                choice = input(c("❯ ", Color.BOLD)).strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if choice.startswith("/quit"):
                return None
            if choice.startswith("/"):
                print(f"  Command not available here. Type a database name/number or /quit.")
                continue
            if choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(dbList):
                    return dbList[idx]
            if choice in dbs:
                return choice
            print(f"  {c(f"'{choice}' is not valid.", Color.RED)} Try a number or name from the list.")
