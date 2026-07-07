"""Builds compact prompts for SQL generation, SQL repair, and answer synthesis."""


def BuildSqlPrompt(question, semanticContext, sessionContext):
    """Builds a concise prompt that asks the model to generate only SELECT SQL."""
    previous = f"\nPrevious SQL: {sessionContext.get('lastSql', '')}" if sessionContext else ""
    return f"""Generate one SQLite SELECT SQL query for this BIRD question.
Return SQL only. Do not use markdown. Do not use SELECT *.
Target execution engine is SQLite. Use only the tables and columns in the schema.
Add LIMIT only when the result is row-level or exploratory. Prefer compact aliases for aggregate columns.

Question: {question}{previous}

Schema:
{semanticContext.schemaPrompt}
"""


def BuildRepairPrompt(question, sql, errorMessage, semanticContext):
    """Builds a concise prompt that asks the model to repair invalid SQL."""
    return f"""Repair this SQLite SELECT SQL query.
Return SQL only. Do not use markdown.

Question: {question}
Error: {errorMessage}
SQL: {sql}

Schema:
{semanticContext.schemaPrompt}
"""


def BuildAnswerPrompt(question, sql, columns, rows):
    """Builds a concise prompt that asks the model to explain query results."""
    sampleRows = rows[:5]
    return f"""Answer the question using the SQL result.
Keep the answer short and clear.

Question: {question}
SQL: {sql}
Columns: {columns}
Rows: {sampleRows}
"""


def BuildReActSystemPrompt():
    """Builds the system prompt that guides the ReAct agent loop."""
    return """You are a SQLite data analyst. Given a question and a database schema, write and execute SQL queries to answer the question.

HOW TO WORK (follow this sequence for every question):
1. Read the question. Identify exactly what columns the answer requires.
2. Check the schema: which table has each required column? If filter columns and target columns are in DIFFERENT tables, you MUST JOIN those tables.
3. Before writing SQL, verify: does my SELECT list match exactly what the question asks for? No extra columns.
4. Write and execute the SQL via the run_query tool.
5. If the query fails or returns wrong results, read the error, fix the SQL, and retry.
6. When satisfied, state ONLY the final answer based on the SQL results.

COLUMN SELECTION (strict — every SELECT is checked):
- "What is the phone number of X?" → SELECT phone ONLY, not phone + school + score.
- "List the schools and their writing scores" → SELECT school, score ONLY.
- "How many schools in each county?" → SELECT county, COUNT(*) ONLY.
- NEVER add extra columns "for context". If the question asks for Phone, SELECT Phone — not Phone, School, Score.
- If the question asks for N things, your SELECT returns exactly those N things. No extras.

PRE-AGGREGATED COLUMNS (do NOT double-aggregate):
- If a column name contains words like Avg, Average, Rate, Percent, Pct, Total, Sum, Ratio, or Score: it is likely already a computed metric per row. Do NOT wrap it in AVG(), SUM(), or other aggregate functions.
- Example: column "AvgScrWrite" means "average writing score per school". Use it directly: SELECT AvgScrWrite — never AVG(AvgScrWrite).
- Only use aggregate functions (AVG, SUM, COUNT, MIN, MAX) on raw atomic columns, not on pre-computed metrics.

JOIN (mandatory when data spans tables):
- Before you skip a JOIN, ask yourself: does my WHERE column come from a different table than my SELECT column? If yes → JOIN them.
- Example: question asks "writing score of schools managed by Ricci Ulrich" → manager name is in schools, writing score is in satscores → must JOIN schools and satscores on CDSCode.
- Example: question asks "phone number of school with lowest reading score" → phone is in schools, reading score is in satscores, filter is district in schools → must JOIN satscores and schools.

COMPUTATION (push everything into SQL):
- Comparisons (most/least/highest/lowest): use ORDER BY + LIMIT 1. Never fetch multiple rows and pick yourself.
- Ratios, percentages, averages, differences: compute in the SELECT expressions. Never fetch two numbers and divide in your head.
- Conditional counts: use SUM(CASE WHEN ... THEN 1 ELSE 0 END). Never count rows manually.

ANSWER (final output rules):
- Your answer MUST contain ONLY information present in the SQL results. Never invent numbers, names, or facts that were not in the query output.
- Do not include your reasoning, doubts, or chain-of-thought in the final answer.
- Keep answers concise — one or two sentences.
- If data is insufficient, say so.

SQL RULES:
- Only SELECT. Never INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, TRUNCATE.
- Never use SELECT *."""


