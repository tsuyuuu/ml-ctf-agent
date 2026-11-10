
import argparse
import hmac
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from agent_core import run_agent
from challenge_runner import load_challenge, prepare_contestant_files
from controller import ToolDispatcher
from flag_verifier import FlagVerifier
from solver_runtime import DockerSolver

BASE = Path(__file__).resolve().parent
IDS_FILE = BASE / "evaluation_ids.txt"
PILOT_RESULTS = BASE / "ctftiny_pilot_results.jsonl"
EVAL_RESULTS = BASE / "results.jsonl"

MODEL = "gpt-oss:120b"
MAX_STEPS = 15
MAX_SECONDS = 300


def selected_ids():
    ids = [
        line.strip()
        for line in IDS_FILE.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate challenge IDs in evaluation_ids.txt")
    if not 3 <= len(ids) <= 10:
        raise ValueError("Select between 3 and 10 challenges")
    return ids


def git_commit(directory):
    return subprocess.check_output(
        ["git", "-C", str(directory), "rev-parse", "HEAD"],
        text=True,
    ).strip()


def existing_slots(path):
    slots = set()
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            slot = (record["challenge_id"], record["trial"])
            if slot in slots:
                raise ValueError(f"Duplicate existing result: {slot}")
            slots.add(slot)
    return slots


def preflight(challenge_id):
    challenge = load_challenge(challenge_id, dataset="ctftiny")
    challenge_dir = Path(challenge.challenge_dir).resolve()

    if not isinstance(challenge.flag, str):
        raise TypeError(
            f"{challenge_id}: requires a non-string benchmark checker"
        )

    if not challenge.files:
        raise ValueError(
            f"{challenge_id}: no contestant files; review setup manually"
        )

    for filename in challenge.files:
        source = (challenge_dir / filename).resolve()
        if not source.is_relative_to(challenge_dir):
            raise ValueError("Contestant file escapes challenge directory")
        if not source.is_file():
            raise FileNotFoundError(source)

    compose_names = (
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    )
    if any((challenge_dir / name).exists() for name in compose_names):
        raise ValueError(
            f"{challenge_id}: service challenge needs separate target setup"
        )

    return challenge


def run_trial(challenge_id, trial, sample_type, tools, api_key):
    challenge = preflight(challenge_id)

    with tempfile.TemporaryDirectory(prefix="ctf_trial_") as temp:
        workspace = Path(temp)
        workspace.chmod(0o755)

        exported = prepare_contestant_files(challenge, workspace)

        # Trusted controller only: never send this to the model.
        expected_flag = challenge.flag

        verifier = FlagVerifier(
            verify_callback=lambda candidate: hmac.compare_digest(
                candidate.strip().encode("utf-8"),
                expected_flag.encode("utf-8"),
            )
        )

        solver = DockerSolver()

        try:
            solver.start(challenge_dir=workspace)

            dispatcher = ToolDispatcher(solver, verifier=verifier)

            result = run_agent(
                challenge_id=challenge_id,
                description=(
                    f"Challenge: {challenge.name}\n"
                    f"Category: {challenge.category}\n"
                    f"Description: {challenge.description}"
                ),
                files=[f"/challenge/{p}" for p in exported],
                execute_tool=dispatcher,
                api_key=api_key,
                tools=tools,
                model=MODEL,
                max_steps=MAX_STEPS,
                max_seconds=MAX_SECONDS,
            )

            result.update({
                "benchmark": "CTFTiny",
                "config_id": "agent",
                "model_id": MODEL,
                "trial": trial,
                "sample_type": sample_type,
                "agent_version": git_commit(BASE),
                "benchmark_commit": git_commit(
                    BASE / "external/CTFTiny"
                ),
                "max_steps": MAX_STEPS,
                "max_seconds": MAX_SECONDS,
                "recorded_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "reset_id": result["run_id"],
                "verified": bool(result.get("verified", False)),
                "submissions_count": len(verifier.submissions),
            })

            return result

        finally:
            solver.stop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode", choices=["pilot", "evaluation"], required=True
    )
    parser.add_argument("--challenge-id")
    parser.add_argument(
        "--check", action="store_true",
        help="Validate challenge setup without using Ollama"
    )
    args = parser.parse_args()

    ids = selected_ids()

    if args.challenge_id and args.challenge_id not in ids:
        parser.error("Challenge ID is not in evaluation_ids.txt")

    chosen = [args.challenge_id] if args.challenge_id else ids

    # Validate all selected challenges before launching attempts.
    for challenge_id in chosen:
        challenge = preflight(challenge_id)
        print(
            f"READY: {challenge_id} "
            f"({challenge.category}; files={challenge.files})"
        )

    if args.check:
        print("Preflight passed. No model calls were made.")
        return

    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        raise RuntimeError("OLLAMA_API_KEY is missing")

    tools = json.loads((BASE / "tools.json").read_text())

    result_path = (
        EVAL_RESULTS if args.mode == "evaluation"
        else PILOT_RESULTS
    )

    completed = existing_slots(result_path)

    for challenge_id in chosen:
        trials = range(1, 4) if args.mode == "evaluation" else [1]

        for trial in trials:
            slot = (challenge_id, trial)

            if slot in completed:
                print(f"SKIPPING existing trial: {slot}")
                continue

            # Pilot results and official results never share a file.
            print(
                f"\n=== {args.mode.upper()} "
                f"{challenge_id} TRIAL {trial} ===",
                flush=True,
            )

            result = run_trial(
                challenge_id,
                trial,
                "live" if args.mode == "evaluation" else "pilot",
                tools,
                api_key,
            )

            with result_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(result) + "\n")

            completed.add(slot)
            print(json.dumps(result, indent=2), flush=True)

    print(f"\nResults saved to: {result_path}")


if __name__ == "__main__":
    main()
