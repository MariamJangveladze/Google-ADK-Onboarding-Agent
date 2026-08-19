"""Deterministic workflow evaluation runner."""

import argparse
import asyncio
import json
from pathlib import Path

from .config import Settings
from .container import build_container


async def evaluate(path: Path) -> dict[str, float | int]:
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    action_passes = 0
    citation_passes = 0
    intervention_passes = 0
    for case in cases:
        container = build_container(Settings(runtime_mode="local"))
        response = None
        for step in case["steps"]:
            if step["type"] == "start":
                response = await container.service.start_employee("U_DEMO", step["email"])
            else:
                response = await container.service.handle_message("U_DEMO", step["message"])
        action_passes += response.action == case["expected_action"]
        citation_passes += not case["requires_citation"] or bool(response.citations)
        intervention_passes += (
            case["expected_action"] != "HELP_ESCALATED" or response.needs_hr_intervention
        )
    total = len(cases)
    return {
        "cases": total,
        "workflow_action_accuracy": action_passes / total,
        "citation_guardrail_accuracy": citation_passes / total,
        "human_escalation_accuracy": intervention_passes / total,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the onboarding workflow")
    parser.add_argument("dataset", nargs="?", default="evals/dataset.jsonl")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(evaluate(Path(args.dataset))), indent=2))


if __name__ == "__main__":
    main()
