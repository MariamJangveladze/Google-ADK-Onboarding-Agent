from pathlib import Path

import pytest

from onboarding_agent.eval_runner import evaluate


@pytest.mark.asyncio
async def test_portfolio_evaluation_guardrails_pass():
    metrics = await evaluate(Path("evals/dataset.jsonl"))
    assert metrics["cases"] == 4
    assert metrics["workflow_action_accuracy"] == 1.0
    assert metrics["citation_guardrail_accuracy"] == 1.0
    assert metrics["human_escalation_accuracy"] == 1.0
