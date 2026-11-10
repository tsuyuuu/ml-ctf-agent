
import argparse
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from challenge_runner import load_challenge, prepare_contestant_files
from agent_core import run_agent
from solver_runtime import DockerSolver
from controller import ToolDispatcher

import hmac
from flag_verifier import FlagVerifier

BASE = Path(__file__).resolve().parent
RESULTS = BASE / "ctftiny_pilot_results.jsonl"


def run_trial(challenge_id, trial, tools, api_key):
    # Fresh challenge object and model conversation
    challenge = load_challenge(challenge_id, dataset="ctftiny")

    with tempfile.TemporaryDirectory(prefix="ctf_trial_") as temp:
        workspace = Path(temp)
        workspace.chmod(0o755)

        exported = prepare_contestant_files(challenge, workspace)

        solver = DockerSolver()

        try:
            # Fresh container and workspace for each trial
            solver.start(challenge_dir=workspace)
            # Answer key stays in the trusted controller.
            expected_flag = challenge.flag

            verifier = FlagVerifier(
                verify_callback=lambda candidate: hmac.compare_digest(
                    candidate.encode("utf-8"),
                    expected_flag.encode("utf-8"),
                )
            )

            dispatcher = ToolDispatcher(solver, verifier=verifier)

            result = run_agent(
                challenge_id=challenge_id,
                description=(
                    f"Challenge: {challenge.name}\n"
                    f"Category: {challenge.category}\n"
                    f"Description: {challenge.description}\n"
                ),
                files=[f"/challenge/{p}" for p in exported],
                execute_tool=dispatcher,
                api_key=api_key,
                tools=tools,
                max_steps=15,
                max_seconds=300,
            )

            result.update({
                "config_id": "agent",
                "trial": trial,
                "sample_type": "pilot",
                "recorded_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "reset_id": result["run_id"],
            })

            return result

        finally:
            solver.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--challenge-id", required=True)
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()

    if args.trials < 1 or args.trials > 3:
        parser.error("Development trials must be between 1 and 3")

    # Only permit challenge IDs in the development dataset.
    # Never fall back to the CTFTiny evaluation dataset.
    try:
        challenge = load_challenge(
        args.challenge_id,
        dataset="ctftiny"
    )
    except (KeyError, ValueError, LookupError) as e:
        parser.error(
            f"Challenge ID is not in the development dataset: "
            f"{args.challenge_id}"
    )

    api_key = os.environ.get("OLLAMA_API_KEY")

    if not api_key:
        raise RuntimeError("OLLAMA_API_KEY is missing")

    all_tools = json.loads((BASE / "tools.json").read_text())

    # No flag submission without a verifier
    tools = all_tools

    for trial in range(1, args.trials + 1):
        print(f"\n=== TRIAL {trial}/{args.trials} ===")

        result = run_trial(
            args.challenge_id,
            trial,
            tools,
            api_key,
        )

        with RESULTS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")

        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
