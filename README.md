# AskData — Natural Language to SQL Agent

AskData is a local text-to-SQL agent that answers natural language questions about databases. It uses an LLM (DeepSeek or any OpenAI-compatible API) to generate, validate, and execute SQL queries in a ReAct (Reasoning + Acting) loop.

**Runs locally. Connects to remote databases. No data leaves your machine except LLM API calls.**

## Quick Start

```bash
# 1. Clone
git clone <repo-url>
cd intern-agents

# 2. Install
uv pip install -e .

# 3. Configure
cp .env.example .env
# Edit .env: add your MODELAPIKEY

# 4. Prepare BIRD dataset (Mini-Dev, ~200MB)
bash scripts/setupbird.sh

# 5. Start chat
uv run askdata chat
```

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- An API key for [DeepSeek](https://platform.deepseek.com/) or any OpenAI-compatible endpoint

## Configuration (`.env`)

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `MODELAPIKEY` | **Yes** | Your LLM API key |
| `MODELBASEURL` | No | API base URL (default: DeepSeek) |
| `MODELNAME` | No | Model name (default: deepseek-chat) |
| `USEMYSQL` | No | Set to `true` to use MySQL instead of SQLite |

## Branches

| Branch | Database | Description |
|---|---|---|
| `main` | BIRD SQLite | Text-to-SQL agent using the BIRD benchmark dataset (500 questions, 11 databases). **No remote server needed.** |
| `feature/mysql-support` | MySQL | Same agent, but connects to a remote MySQL server. Supports real application databases with live schemas. |

### Switch between branches

```bash
# BIRD SQLite (local data only)
git checkout main
uv run askdata prepare-bird --force
uv run askdata chat

# MySQL (remote server)
git checkout feature/mysql-support
# Edit .env: set USEMYSQL=true and fill MYSQL* variables
uv run askdata chat
```

## Preparing the BIRD Dataset (`main` branch)

```bash
# Automatic: download + prepare
bash scripts/setupbird.sh

# Or step by step:
bash scripts/setupbird.sh       # Mini-Dev (500 Qs, 11 DBs, ~200MB)
bash scripts/setupbird.sh full  # Full Dev (1534 Qs, 73 DBs, ~33GB)

# Re-prepare after schema changes:
uv run askdata prepare-bird --force
```

The script downloads BIRD questions from HuggingFace and SQLite database files from the BIRD benchmark's official OSS mirror. Processed schema files are cached in `data/bird/processed/`.

## CLI Commands

```bash
uv run askdata chat              # Interactive REPL
uv run askdata chat -d <db>      # Force a specific database
uv run askdata serve             # Start FastAPI server (port 8000)
uv run askdata prepare-bird      # Prepare BIRD data
uv run askdata gen-instructions  # Generate per-DB context files
uv run askdata smoke             # Run smoke test
```

### Chat REPL Commands

| Command | Action |
|---|---|
| `/examples [simple\|moderate\|challenging\|all]` | Show sample questions |
| `/databases` | List available databases |
| `/use <db>` | Switch database |
| `/use auto` | Auto-detect database from question |
| `/reset` | Clear conversation context |
| `/clear` | Clear terminal screen |
| `/quit` | Exit |

## Architecture

```
CLI (Typer) or API (FastAPI)
  └─ QueryService
       └─ ReActAgent (LLM tool-calling loop)
            ├─ run_query tool (validate → execute)
            ├─ Skills (reusable SQL patterns)
            └─ Context-as-Code (per-DB instructions)
```

The agent uses a ReAct loop: it reasons about the question, calls the `run_query` tool to execute SQL, reads results, and iterates until it can answer. See `askdata/agent/react_agent.py`.

### Key Features

- **Schema auto-detection**: matches question keywords to database tables and columns
- **Skills system**: pre-built SQL patterns for common analysis tasks (compare periods, ratio analysis, rank/top-N) — see `askdata/skills/`
- **Context-as-Code**: per-database `instructions.md` files for business term mappings and JOIN hints — see `data/bird/instructions/`
- **SQL validation**: validates all generated SQL before execution (rejects non-SELECT, `SELECT *`, multi-statement)
- **Self-correction**: on query failure, the error is fed back to the LLM for repair

## Project Structure

```
askdata/
  agent/          ReAct agent loop, LLM client, prompts
  api/            FastAPI routes
  app/            QueryService, SessionStore
  bird/           BIRD dataset loader, schema index, evaluator
  chat_session.py Interactive CLI REPL
  cli.py          Typer CLI entry point
  core/           Config, error types
  db/             Database engine, MySQL loader
  schemas/        Pydantic models (query, SQL, BIRD, semantic)
  skills/         Reusable analysis skill patterns
  spider/         Spider dataset (planned)
  tools/          SQL validator, executor, analyzer, chart builder
data/
  bird/
    instructions/ Per-DB business context (editable)
    processed/    Processed schema cache
    raw/          Raw BIRD data
scripts/
  setupbird.sh    BIRD dataset download script
  geninstructions.py  Context file generator
  smoketest.py    Smoke test
```

## API

Start the server and query via HTTP:

```bash
uv run askdata serve
curl -X POST http://127.0.0.1:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How many accounts?", "databaseId": "financial", "sessionId": "test"}'
```
