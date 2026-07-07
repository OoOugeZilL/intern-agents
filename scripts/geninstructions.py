"""Generates per-database instructions.md files from processed schema data."""

import json
from pathlib import Path


def Generate(processedDir, outDir):
    databases = json.loads((Path(processedDir) / "databases.json").read_text(encoding="utf-8"))
    questions = json.loads((Path(processedDir) / "questions.json").read_text(encoding="utf-8"))
    outPath = Path(outDir)
    outPath.mkdir(parents=True, exist_ok=True)

    for db in databases:
        dbQuestions = [q for q in questions if q.get("databaseId") == db["databaseId"]]
        sampleQuestions = [q["question"] for q in dbQuestions[:5]]

        lines = [f"# {db['databaseId']} — Business Context", ""]
        lines.append("## Sample Questions (from dataset)")
        for q in sampleQuestions:
            lines.append(f"- {q}")
        lines.append("")

        if db.get("tables"):
            lines.append("## Tables & Columns")
            for table in db["tables"]:
                lines.append(f"\n### {table['tableName']}")
                for col in table.get("columns", []):
                    pk = " (PK)" if col.get("isPrimary") else ""
                    lines.append(f"- `{col['columnName']}` {col.get('columnType', 'text')}{pk}")
            lines.append("")

        if db.get("foreignKeys"):
            lines.append("## JOIN Patterns")
            for fk in db["foreignKeys"]:
                lines.append(f"- `{fk['leftTable']}.{fk['leftColumn']}` = `{fk['rightTable']}.{fk['rightColumn']}`")
            lines.append("")

        lines.append("## Business Term Mappings")
        lines.append("_Add domain-specific mappings below. Format: `\"natural language term\" → SQL expression`_")
        lines.append("")
        lines.append("```")
        lines.append("# Example:")
        lines.append('# "active customer" → status = \'active\'')
        lines.append('# "last month" → date >= date(\'now\', \'-30 days\')')
        lines.append("```")
        lines.append("")
        lines.append("<!-- Add your mappings above this line -->")

        (outPath / f"{db['databaseId']}.md").write_text("\n".join(lines), encoding="utf-8")

    return len(databases)


if __name__ == "__main__":
    count = Generate("data/bird/processed", "data/bird/instructions")
    print(f"Generated {count} instructions files in data/bird/instructions/")
