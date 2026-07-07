"""Loads and manages reusable analysis skills for the agent."""

from pathlib import Path


class SkillLoader:
    """Loads skill markdown files and provides their content to the agent."""

    def __init__(self, skillsDir=None):
        self.skillsDir = Path(skillsDir) if skillsDir else Path(__file__).parent
        self._skills = None

    def LoadAll(self):
        if self._skills is not None:
            return self._skills
        self._skills = {}
        if not self.skillsDir.exists():
            return self._skills
        for path in sorted(self.skillsDir.glob("*.md")):
            name = path.stem
            self._skills[name] = path.read_text(encoding="utf-8")
        return self._skills

    def BuildPromptSection(self):
        """Returns a compact prompt section listing available skills with their SQL patterns."""
        skills = self.LoadAll()
        if not skills:
            return ""

        lines = ["AVAILABLE ANALYSIS SKILLS (reference these patterns when applicable):"]
        for name, content in skills.items():
            desc = self._ExtractSection(content, "## Description")
            when = self._ExtractSection(content, "## When to Use")
            sqlPattern = self._ExtractCodeBlock(content)
            lines.append(f"\nSkill: {name}")
            if desc:
                lines.append(f"  {desc}")
            if when:
                lines.append(f"  When: {when}")
            if sqlPattern:
                lines.append(f"  Pattern: {sqlPattern[:300]}")
        return "\n".join(lines)

    def _ExtractSection(self, content, heading):
        lines = content.split("\n")
        inSection = False
        result = []
        for line in lines:
            if line.strip() == heading:
                inSection = True
                continue
            if inSection:
                if line.strip().startswith("##"):
                    break
                stripped = line.strip()
                if stripped and not stripped.startswith("```"):
                    result.append(stripped.strip("- "))
        return " ".join(result[:2]) if result else None

    def _ExtractCodeBlock(self, content):
        lines = content.split("\n")
        inBlock = False
        sqlLines = []
        for line in lines:
            if line.strip().startswith("```sql"):
                inBlock = True
                continue
            if inBlock:
                if line.strip() == "```":
                    break
                sqlLines.append(line.strip())
        return " ".join(sqlLines) if sqlLines else None
