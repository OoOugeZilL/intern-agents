# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install the package in editable mode
uv pip install -e .

# Download and prepare BIRD dataset (default: Mini-Dev, 500 Qs, ~200MB)
bash scripts/setupbird.sh

# Or download the Full Dev split (1534 Qs, ~33GB)
bash scripts/setupbird.sh full

# Prepare BIRD data manually (Mini-Dev)
uv run askdata prepare-bird --rawdir data/bird/raw --outdir data/bird/processed --demodir data/bird/demo --force

# Prepare BIRD data manually (Full Dev)
uv run askdata prepare-bird --rawdir data/bird/raw --outdir data/bird/processed --demodir data/bird/demo --force --split dev

# Run the FastAPI server (with hot reload)
uv run askdata serve --reload

# Run the smoke test
uv run askdata smoke

# Run pytest (when tests are added)
uv run pytest
```

## Architecture

This is a **text-to-SQL backend** that answers natural language questions about relational data. It targets the [BIRD benchmark](https://bird-bench.github.io/) and generates SQLite SQL via an LLM (DeepSeek by default), validates it, executes it, and returns results with chart recommendations.

### Layered structure

```
CLI (askdata/cli.py, Typer)
  └─ API (askdata/api/, FastAPI)
       └─ Service (askdata/app/queryservice.py)
            └─ Agent Graph (askdata/agent/graph.py)
                 ├─ LlmClient (OpenAI-compatible, calls DeepSeek)
                 ├─ SqlValidator (sqlglot-based, SELECT-only, adds LIMIT)
                 ├─ SqlExecutor (SQLAlchemy against SQLite)
                 ├─ ResultAnalyzer (deterministic summary from rows)
                 └─ ChartBuilder (rule-based chart recommendation)
```

### Agent flow (V1 controlled, not LangGraph)

`AgentGraph.Run()` — `askdata/agent/graph.py:25` — executes a fixed pipeline:

1. **Retrieve schema** — `BirdSchemaIndex` token-matches question words against table/column names. Falls back to first 8 tables if no match.
2. **Generate SQL** — `LlmClient.Complete()` sends a compact prompt with the schema. Returns raw model text, cleaned of markdown wrappers.
3. **Validate** — `SqlValidator` rejects non-SELECT, multi-statement, `SELECT *`. Applies `LIMIT 20` if unbounded, caps existing LIMIT at 100.
4. **Execute** — `SqlExecutor` runs via SQLAlchemy against a SQLite file.
5. **Repair loop** — On validation or execution failure, sends a repair prompt to the LLM (one retry per failure type).
6. **Analyze + Chart** — Deterministic row count/summary + rule-based chart type detection (line for time series, bar for categories, etc.).
7. **Answer** — LLM synthesizes a natural language answer from the results.

### Data preparation

`BirdPrep` reads raw BIRD SQLite databases, inspects each schema via `PRAGMA` calls, and writes three processed JSON files:
- `databases.json` — schema definitions (tables, columns, primary/foreign keys)
- `questions.json` — all questions with evidence and gold SQL
- `goldsql.json` — question ID to gold SQL mapping

The `--split` option selects which question file to read: `mini_dev_sqlite` (default, Mini-Dev) or `dev` (Full Dev). Both splits use the same question JSON format (`question_id`, `db_id`, `question`, `evidence`, `SQL`, `difficulty`). The database directory (`dev_databases/`) structure is identical across splits.

`BirdLoader.FindBirdRoot()` searches for the question JSON across multiple candidate paths to handle different download source layouts (OSS zip, HuggingFace, GitHub sparse checkout).

### Configuration

`askdata/core/config.py` uses Pydantic `BaseSettings` with `.env` file. Environment variables:
- `MODEL_BASE_URL`, `MODEL_NAME`, `MODEL_API_KEY` — LLM endpoint (defaults to DeepSeek)
- `DATABASE_URL` — SQLAlchemy URL fallback
- `BIRD_RAW_DIR`, `BIRD_PROCESSED_DIR`, `BIRD_DEMO_DIR`

### Session handling

`SessionStore` (`askdata/app/sessionstore.py`) is an in-memory dict keyed by session ID. It persists the previous question, SQL, and columns for follow-up context — no database.

### Key constraints

- Only SQLite dialect. Only SELECT statements. No `SELECT *`.
- The LLM client uses `temperature=0` for deterministic SQL generation.
- Schema retrieval is token-based, not embedding-based — no vector store.
- The spider module (`askdata/spider/`) has `__pycache__` artifacts but no `.py` source files — it is not yet implemented.
