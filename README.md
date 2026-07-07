# AskData — Natural Language to SQL Agent

AskData answers natural language questions about databases. It uses an LLM to write, validate, and execute SQL in a ReAct loop.

**LLM runs locally. Database can be local SQLite or remote MySQL. No data sent anywhere except LLM API calls.**

## Quick Start

```bash
git clone git@github.com:OoOugeZilL/intern-agents.git
cd intern-agents
cp .env.example .env        # edit .env: add your MODELAPIKEY
uv pip install -e .
bash scripts/setupbird.sh   # download BIRD dataset (~200MB)
uv run askdata chat
```

## Project Structure

```
intern-agents/
  askdata/                  # Python package (all backend code)
    agent/                  # ReAct agent loop, LLM client, prompts
      react_agent.py        #   main agent: tool-calling loop
      llmclient.py          #   OpenAI-compatible Chat/Complete
      prompts.py            #   system prompt + rules
      graph.py              #   [deprecated] old V1 fixed pipeline
    app/                    # Service layer
      queryservice.py       #   QueryService: schema + agent orchestration
      sessionstore.py       #   in-memory session context
    api/                    # FastAPI routes (frontend calls these)
      main.py               #   app factory, /health
      queryroutes.py        #   POST /api/query, POST /api/sessions/{id}/reset
      birdroutes.py         #   GET /api/bird/databases, /questions, /evaluate
    core/                   # Config + error types
      config.py             #   pydantic Settings, .env loading
      errors.py             #   AppError, DataError, SqlError, ModelError
    db/                     # Database adapters
      engine.py             #   SQLAlchemy engine factory
      mysql_loader.py       #   MySQL schema loader (feature/mysql-support only)
    bird/                   # BIRD dataset: loader, schema index, evaluator
    schemas/                # Pydantic models (QueryRequest, QueryResponse, etc.)
    skills/                 # Reusable SQL pattern templates
    tools/                  # SqlValidator, SqlExecutor, ResultAnalyzer, ChartBuilder
    chat_session.py         # CLI chat REPL
    cli.py                  # Typer entry point
  frontend/                 # Frontend code goes here (see below)
  scripts/                  # Shell scripts + smoke test
  data/                     # BIRD dataset (gitignored, generated locally)
    bird/
      raw/                  #   downloaded SQLite DBs + question JSON
      processed/            #   cached schema (databases.json, questions.json)
      instructions/         #   per-DB business context (hand-edited)
      demo/                 #   demo question subset
```

## Branches

| Branch | DB | When to use |
|---|---|---|
| `main` | BIRD SQLite (local) | Daily development. Download data once, offline. |
| `feature/mysql-support` | MySQL (remote) | When you need real application DB. Set `USEMYSQL=true` in `.env`. |

Switch: `git checkout <branch>` — code API is identical between branches.

### Branch diff summary

`feature/mysql-support` adds exactly two things on top of `main`:
1. `askdata/db/mysql_loader.py` — reads schema from `information_schema`
2. `QueryService.EnsureSchemaIndex()` — picks MySQL loader when `USEMYSQL=true`

Everything else (agent, tools, prompts, API routes, chat CLI) is shared.

## Config (.env)

Copy `.env.example` to `.env`. Only `MODELAPIKEY` is required.

Env var names are **case-insensitive**, matched against pydantic Settings fields. Both `MODELAPIKEY` and `MODEL_API_KEY` work. See `askdata/core/config.py` for the full mapping.

| Var | Required | Default | Description |
|---|---|---|---|
| `MODELAPIKEY` | **Yes** | — | LLM API key |
| `MODELBASEURL` | No | `api.deepseek.com` | API base URL |
| `MODELNAME` | No | `deepseek-chat` | Model name |
| `DATABASEURL` | No | — | Fallback SQLite URL |
| `BIRDRAWDIR` | No | `data/bird/raw` | Raw BIRD data dir |
| `BIRDPROCESSEDDIR` | No | `data/bird/processed` | Processed schema cache |
| `BIRDDEMODIR` | No | `data/bird/demo` | Demo questions dir |
| `BIRDINSTRUCTIONSDIR` | No | `data/bird/instructions` | Per-DB context files |

## Coding Rules

- **Style**: follow the code already in the repo. One-line docstrings. No comments unless the WHY is non-obvious.
- **No security over-engineering**: this is an internal tool. Don't add auth middleware, input sanitization layers, or rate limiting unless there's a real attack surface. The only external input is LLM API calls.
- **Compact**: prefer one file with a clear purpose over a directory of tiny files. A 200-line module is fine. A 40-line module that only gets imported once is not.
- **Don't guess**: if a function can fail, let it raise. Don't wrap everything in try/except "just in case." Handle errors at the boundary (API route).
- **New code in `askdata/`**: all Python code goes under the `askdata` package. Scripts that shouldn't be imported go in `scripts/`.
- **Tests**: `uv run askdata smoke` is the smoke test. Run it before pushing. We don't have unit tests yet — add them under `tests/` when you do.

## CLI Chat (Backend Debug Tool Only)

```bash
uv run askdata chat              # auto-detect database
uv run askdata chat -d financial # force a specific DB
```

**This is for backend debugging.** It's a terminal REPL so backend devs can test agent behavior without curl. It is NOT the product UI. Frontend should call the HTTP API.

Other useful CLI commands:

```bash
uv run askdata serve            # start API server at :8000
uv run askdata smoke            # smoke test (imports + validation)
uv run askdata prepare-bird     # re-prepare BIRD data
uv run askdata gen-instructions # regenerate per-DB context files
```

## Frontend API

The backend exposes a REST API at `http://127.0.0.1:8000`. Start it with `uv run askdata serve`.

### POST /api/query

Ask a natural language question.

**Request** (JSON):
```json
{
  "question": "How many accounts are in the financial database?",
  "databaseId": "financial",
  "sessionId": "default",
  "showSql": true,
  "showTrace": true
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `question` | string | **Yes** | Natural language question |
| `databaseId` | string | **Yes** | Which database to query |
| `sessionId` | string | No | For follow-up context. Default: `"default"` |
| `showSql` | bool | No | Return the generated SQL. Default: `true` |
| `showTrace` | bool | No | Return agent reasoning trace. Default: `true` |

**Response** (200):
```json
{
  "question": "How many accounts?",
  "databaseId": "financial",
  "answer": "There are 4,500 accounts in the financial database.",
  "sql": "SELECT COUNT(*) FROM account",
  "executionStatus": "executed",
  "columns": ["count"],
  "rows": [{"count": 4500}],
  "chart": {"chartType": "table", "title": "Result", "reason": "..."},
  "analysis": {"rowCount": 1, "summary": "The result is 4500."},
  "trace": [{"step": "ExecuteSql", "status": "success", "message": "Returned 1 rows."}],
  "error": null
}
```

**Error responses** (non-200):
| Status | `error.code` | Meaning |
|---|---|---|
| 400 | `DataError` | Invalid database ID, missing data |
| 422 | `SqlError` | SQL execution or validation failed |
| 502 | `ModelError` | LLM API call failed |
| 500 | `AppError` | Unknown internal error |

### GET /health

```json
{"ok": true}
```

### GET /api/bird/databases

List available databases with table and question counts.

### GET /api/bird/questions?databaseId=financial

List BIRD questions for a database (includes gold SQL for evaluation).

### Frontend Code

Put all frontend code in the `frontend/` folder at repo root. The backend serves nothing — frontend and backend are fully decoupled.

```
frontend/
  index.html
  app.js
  style.css
```

The API server listens on `127.0.0.1:8000` by default. Frontend just calls it. No CORS needed if frontend is served from the same origin; otherwise add CORS middleware in `askdata/api/main.py`.

## Preparing BIRD Data

```bash
bash scripts/setupbird.sh        # Mini-Dev (500 Qs, 11 DBs, ~200MB)
bash scripts/setupbird.sh full   # Full Dev (1534 Qs, ~33GB)
```

The script downloads questions from HuggingFace (`birdsql/bird_mini_dev`) and databases from the BIRD benchmark OSS mirror. Processed schema is cached in `data/bird/processed/`. Raw data and processed cache are both gitignored — each developer runs this once locally.

Regenerate after schema changes:
```bash
uv run askdata prepare-bird --force
uv run askdata gen-instructions
```

## Architecture

```
CLI (chat) or HTTP (API)
       │
  QueryService
       │
  BirdSchemaIndex ──→ ReActAgent ──→ LlmClient (LLM API)
       │                   │
  [schema + context]   [tool loop]
                           │
                     run_query(sql)
                      │         │
                 SqlValidator  SqlExecutor → DB
```

The agent uses OpenAI function-calling:
1. LLM receives question + schema + skill patterns
2. LLM reasons, writes SQL, calls `run_query(sql)` tool
3. Tool validates (rejects non-SELECT, `SELECT *`, etc.) then executes
4. Results (or error) go back to LLM
5. LLM reasons again — may retry with fixed SQL, run another query, or produce final answer
6. Loops until answer or max 8 iterations

Context the agent sees per question:
- System prompt with rules (column selection, JOINs, computation, etc.)
- Available skills (SQL patterns for ratio, comparison, ranking)
- Per-DB instructions (`data/bird/instructions/<db>.md`) — hand-edited business term mappings

## Skills System

Reusable SQL patterns in `askdata/skills/`. The agent sees them as reference templates. Current skills:

| Skill | For questions like |
|---|---|
| `compare-periods` | "How did X change between A and B?" |
| `ratio-analysis` | "What is the ratio of X to Y?" |
| `rank-top-bottom` | "Which X has the most/least Y?" |

Add a new skill: drop a markdown file in `askdata/skills/`, follow the format of existing files. Auto-loaded on next agent start.

## Context-as-Code

Per-database instructions in `data/bird/instructions/<db>.md`. Hand-edited. The agent loads these as part of the schema context.

Example (`california_schools.md`):
```markdown
## Business Term Mappings
- "State Special School" → EdOpsCode = 'SSS'
- "charter school" → Charter = 1
- "SAT excellence rate" → NumGE1500 / NumTstTakr
```

Regenerate skeleton files with `uv run askdata gen-instructions`.
