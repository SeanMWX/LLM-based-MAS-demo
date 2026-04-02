from __future__ import annotations

import argparse
import json
from typing import Any

from .models import Scenario


def print_scenarios(_demo: Any, scenarios: dict[str, Scenario]) -> None:
    for scenario in scenarios.values():
        print(f"{scenario.id:<24} {scenario.title}")


def render_scenario(demo: Any, scenario: Scenario) -> None:
    print(
        json.dumps(
            {
                "id": scenario.id,
                "title": scenario.title,
                "user_task": scenario.user_task,
                "repository_context": scenario.repository_context,
                "acceptance_criteria": scenario.acceptance_criteria,
                "available_tools": scenario.available_tools,
                "risk_notes": scenario.risk_notes,
                "test_command": scenario.test_command,
                "start_role": scenario.start_role,
                "seed_context": scenario.seed_context,
                "seeded_roles": sorted(
                    set((scenario.seed_role_outputs or {}).keys())
                    | set((scenario.seed_role_artifacts or {}).keys())
                ),
                "role_order": demo.role_order,
            },
            indent=2,
            ensure_ascii=False,
        )
    )


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List scenarios.")

    render_parser = subparsers.add_parser("render", help="Render one scenario.")
    render_parser.add_argument("--case", required=True, help="Scenario id.")

    run_parser = subparsers.add_parser("run", help="Run one or all scenarios.")
    run_parser.add_argument("--case", default="all", help="Scenario id or 'all'.")
    run_parser.add_argument(
        "--invoke",
        action="store_true",
        help="Invoke a real model if API keys are configured.",
    )
    run_parser.add_argument(
        "--model",
        default=None,
        help="Optional model override.",
    )
    run_parser.add_argument(
        "--repo-path",
        default=None,
        help="Optional real repository path for read-only observation.",
    )
    run_parser.add_argument(
        "--test-command",
        default=None,
        help="Optional real test command to execute during the tester step.",
    )
    run_parser.add_argument(
        "--test-timeout",
        type=int,
        default=120,
        help="Timeout in seconds for the real test command.",
    )
    run_parser.add_argument(
        "--seed-file",
        default=None,
        help="Optional JSON file with seeded artifacts, test results, and start role.",
    )
    run_parser.add_argument(
        "--start-role",
        default=None,
        help="Optional role to start from, such as tester or reviewer.",
    )

    return parser.parse_args()


def resolve_requested_scenarios(
    requested: str,
    scenarios: dict[str, Scenario],
) -> list[Scenario]:
    if requested == "all":
        return list(scenarios.values())
    if requested not in scenarios:
        raise KeyError(f"Unknown scenario id: {requested}")
    return [scenarios[requested]]


def main(demo: Any) -> None:
    args = parse_args(demo.description)
    scenarios = demo.load_scenarios()

    if args.command == "list":
        print_scenarios(demo, scenarios)
        return

    if args.command == "render":
        render_scenario(demo, scenarios[args.case])
        return

    requested = resolve_requested_scenarios(args.case, scenarios)
    seed_payload = demo.load_seed_payload(args.seed_file)
    results = [
        demo.summarize_state(
            demo.run_scenario(
                scenario,
                invoke_model=args.invoke,
                model_name=args.model,
                repo_path=args.repo_path,
                test_command=args.test_command,
                test_timeout_sec=args.test_timeout,
                seed_payload=seed_payload,
                start_role=args.start_role,
            )
        )
        for scenario in requested
    ]
    print(json.dumps(results, indent=2, ensure_ascii=False))
