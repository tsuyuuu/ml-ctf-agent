
import argparse
import json
import os
import shutil
import tempfile
from pathlib import Path

from nyuctf.dataset import CTFDataset
from nyuctf.challenge import CTFChallenge

from agent_core import run_agent
from solver_runtime import DockerSolver
from controller import ToolDispatcher


BASE_DIR = Path(__file__).resolve().parent

DEV_DATASET = (
    BASE_DIR / "external"
    / "NYU_CTF_Bench"
    / "development_dataset.json"
)

TOOLS_FILE = BASE_DIR / "tools.json"


def load_challenge(challenge_id):
    """
    Load a development challenge in the trusted controller.
    Never expose the full challenge object to the solver.
    """
    dataset = CTFDataset(dataset_json=str(DEV_DATASET))
    challenge = CTFChallenge(
        dataset.get(challenge_id),
        dataset.basedir
    )

    return challenge


def prepare_contestant_files(challenge, workspace):
    """
    Export only authorized contestant files.

    Do not copy challenge.json, hidden source,
    build files, or verifier metadata.
    """
    exported = []

    for filename in challenge.files:
        source = Path(challenge.challenge_dir) / filename

        if not source.is_file():
            raise FileNotFoundError(
                f"Missing contestant file: {filename}"
            )

        destination = workspace / filename
        destination.parent.mkdir(
            parents=True, exist_ok=True
        )

        shutil.copy2(source, destination)

        # Make exported contestant files readable by ctfuser.
        # Do not grant write access.
        destination.chmod(0o644)

        exported.append(filename)

    return exported


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--challenge-id",
        required=True
    )

    args = parser.parse_args()

    api_key = os.environ.get("OLLAMA_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OLLAMA_API_KEY not configured"
        )

    challenge = load_challenge(args.challenge_id)

    tools = json.loads(TOOLS_FILE.read_text())

    # Exclude flag verification until approved
    # private evaluator is integrated.
    tools = [
        tool for tool in tools
        if tool["function"]["name"]
        != "submit_flag"
    ]

    # Fresh workspace for each development attempt
    with tempfile.TemporaryDirectory(
        prefix="ctf_contestant_"
    ) as temporary_dir:

        workspace = Path(temporary_dir)

        # TemporaryDirectory defaults to mode 700.
        # Allow the unprivileged solver to traverse the mounted directory.
        workspace.chmod(0o755)

        exported = prepare_contestant_files(
            challenge, workspace
        )

        solver = DockerSolver()

        try:
            solver.start(
                challenge_dir=workspace
            )

            dispatcher = ToolDispatcher(solver)

            result = run_agent(
                challenge_id=args.challenge_id,
                description=(
                    f"Challenge: {challenge.name}\n"
                    f"Category: {challenge.category}\n"
                    f"Description: {challenge.description}\n"
                    "The permitted files are mounted "
                    "read-only under /challenge.\n"
                    "Flag verification is unavailable "
                    "for this development test."
                ),
                files=[
                    f"/challenge/{filename}"
                    for filename in exported
                ],
                execute_tool=dispatcher,
                api_key=api_key,
                tools=tools,
                max_steps=15,
                max_seconds=300
            )

            print("\n=== RUN SUMMARY ===")
            print(json.dumps(result, indent=2))

        finally:
            solver.stop()


if __name__ == "__main__":
    main()
