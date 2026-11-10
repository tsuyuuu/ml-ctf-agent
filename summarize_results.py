
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev

BASE = Path(__file__).resolve().parent
RESULTS = BASE / "results.jsonl"
IDS_FILE = BASE / "evaluation_ids.txt"

SUMMARY_JSON = BASE / "summary.json"
SUMMARY_CSV = BASE / "per_challenge.csv"

EXPECTED_TRIALS = {1, 2, 3}
INCIDENT_STATUSES = {
    "model_error",
    "infrastructure_error",
    "scope_violation",
    "setup_error",
}


def load_records():
    records = [
        json.loads(line)
        for line in RESULTS.read_text().splitlines()
        if line.strip()
    ]

    if not records:
        raise ValueError("No evaluation records found")

    return records


def token_mean(rows, field):
    values = [r.get(field) for r in rows]
    if any(v is None for v in values):
        return None
    return mean(values)


def summarize_challenge(challenge_id, rows):
    trials = [r["trial"] for r in rows]

    if len(trials) != len(set(trials)):
        raise ValueError(
            f"Duplicate trial records for {challenge_id}"
        )

    complete = (
        set(trials) == EXPECTED_TRIALS
        and len(rows) == 3
    )

    incidents = [
        r["status"]
        for r in rows
        if r["status"] in INCIDENT_STATUSES
    ]

    outcomes = [
        int(r.get("verified", False))
        for r in rows
    ]

    mean_input = token_mean(rows, "input_tokens")
    mean_output = token_mean(rows, "output_tokens")

    result = {
        "challenge_id": challenge_id,
        "attempts": len(rows),
        "successes": sum(outcomes),
        "trial_outcomes": {
            str(r["trial"]): bool(r.get("verified", False))
            for r in rows
        },
        "incidents": incidents,
        "complete": complete and not incidents,
        "success_rate_pct": (
            100 * mean(outcomes) if complete else None
        ),
        "sample_sd_pp": (
            100 * stdev(outcomes) if complete else None
        ),
        "mean_input_tokens": (
            mean_input if complete else None
        ),
        "mean_output_tokens": (
            mean_output if complete else None
        ),
        "mean_total_tokens": (
            mean_input + mean_output
            if complete
            and mean_input is not None
            and mean_output is not None
            else None
        ),
        "mean_elapsed_s": (
            mean(r["elapsed_s"] for r in rows)
            if complete else None
        ),
    }

    return result


def main():
    ids = [
        line.strip()
        for line in IDS_FILE.read_text().splitlines()
        if line.strip()
    ]

    records = load_records()
    grouped = defaultdict(list)

    for record in records:
        if record.get("sample_type") != "live":
            raise ValueError("Non-live record in results.jsonl")

        if record.get("config_id") != "agent":
            raise ValueError("Unexpected configuration")

        if record["challenge_id"] not in ids:
            raise ValueError("Unexpected challenge ID")

        grouped[record["challenge_id"]].append(record)

    summary = [
        summarize_challenge(challenge_id, grouped[challenge_id])
        for challenge_id in ids
    ]

    overall_complete = all(
        row["complete"] for row in summary
    )

    total_successes = sum(r["successes"] for r in summary)
    total_attempts = sum(r["attempts"] for r in summary)

    output = {
        "benchmark": "CTFTiny",
        "config_id": "agent",
        "total_attempts": total_attempts,
        "total_successes": total_successes,
        "overall_complete": overall_complete,
        "observed_successes_per_attempt_pct": (
            100 * total_successes / total_attempts
            if total_attempts else None
        ),
        "overall_success_rate_pct": (
            100 * total_successes / (3 * len(ids))
            if overall_complete else None
        ),
        "challenges": summary,
    }

    SUMMARY_JSON.write_text(
        json.dumps(output, indent=2)
    )

    columns = list(summary[0].keys())

    with SUMMARY_CSV.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(summary)

    print(json.dumps(output, indent=2))
    print("\nSaved summary.json and per_challenge.csv")


if __name__ == "__main__":
    main()
