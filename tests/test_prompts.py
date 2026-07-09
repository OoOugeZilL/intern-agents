from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from askdata.agent.prompts import BuildReActSystemPrompt


def test_react_prompt_allows_evidence_directed_aggregation_of_precomputed_metrics():
    prompt = BuildReActSystemPrompt()

    assert "If the schema evidence defines a formula" in prompt
    assert "sum(average math scores) / count(schools)" in prompt
