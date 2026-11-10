"""The code was generated with AI assistance to produce benchmark summaries,
CSV tables, and plots from recorded attempts.
"""

import csv
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, stdev, variance
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = Path(__file__).resolve().parent
RESULTS = BASE / "results" / "evaluation" / "results.jsonl"
IDS_FILE = BASE / "evaluation_ids.txt"

SUMMARY_JSON = BASE / "results" / "evaluation" / "summary.json"
SUMMARY_CSV = BASE / "results" / "evaluation" / "per_challenge.csv"
ATTEMPTS_CSV = BASE / "results" / "evaluation" / "per_attempt.csv"
PASS_CSV = BASE / "results" / "evaluation" / "pass_at_k.csv"
TRIAL_CSV = BASE / "results" / "evaluation" / "per_trial.csv"
PASS_PNG = BASE / "results" / "evaluation" / "pass_at_k.png"
SOLVE_PNG = BASE / "results" / "evaluation" / "solve_rate_variance.png"

EXPECTED_TRIALS = {1, 2, 3}

# These statuses mark evaluation completeness as unresolved.
INCIDENT_STATUSES = {
    "model_error",
    "infrastructure_error",
    "scope_violation",
    "setup_error",
}

# One frozen configuration was used for the official evaluation.
EXPECTED_CONFIG = "agent"


def load_records():
    records = [
        json.loads(line)
        for line in RESULTS.read_text().splitlines()
        if line.strip()
    ]

    if not records:
        raise ValueError("No evaluation records found")

    return records

# Missing measurements make the aggregate unavailable
def average(rows, field):
    values = [r.get(field) for r in rows]

    if not values or any(v is None for v in values):
        return None

    return mean(values)


def total(rows, field):
    values = [r.get(field) for r in rows]

    if not values or any(v is None for v in values):
        return None

    return sum(values)


def known_tokens(record, field):
    # Known counts may omit failed API requests that returned no usage data.
    return record.get(
        f"known_{field}_tokens",
        record.get(f"{field}_tokens"),
    )


def token_average(rows, field):
    values = [known_tokens(r, field) for r in rows]

    if any(v is None for v in values):
        return None

    return mean(values)


def token_total(rows, field):
    values = [known_tokens(r, field) for r in rows]

    if any(v is None for v in values):
        return None

    return sum(values)


def pass_at_k(n, c, k):
    """
    Standard pass@k estimator:

    1 - C(n-c, k) / C(n, k)

    n = recorded trials
    c = verified successes
    k = number of attempts
    """
    if n < k or k < 1:
        return None

    if n - c < k:
        return 1.0

    return 1 - math.comb(n - c, k) / math.comb(n, k)


def summarize_challenge(challenge_id, rows):
    rows = sorted(rows, key=lambda r: r["trial"])

    trials = [r["trial"] for r in rows]

    if len(trials) != len(set(trials)):
        raise ValueError(
            f"Duplicate trial records for {challenge_id}"
        )

    if not set(trials).issubset(EXPECTED_TRIALS):
        raise ValueError(
            f"Unexpected trial number for {challenge_id}"
        )

    # Trial coverage and incident status are separate:
    # all three records may exist while the evaluation remains incomplete.
    slots_complete = (
        set(trials) == EXPECTED_TRIALS
        and len(rows) == len(EXPECTED_TRIALS)
    )

    incidents = [
        r["status"]
        for r in rows
        if r["status"] in INCIDENT_STATUSES
    ]

    outcomes = [
        int(bool(r.get("verified", False)))
        for r in rows
    ]

    n = len(outcomes)
    successes = sum(outcomes)

    mean_input = token_average(rows, "input")
    mean_output = token_average(rows, "output")
    total_input = token_total(rows, "input")
    total_output = token_total(rows, "output")

    success_rate = 100 * mean(outcomes) if slots_complete else None

    result = {
        "challenge_id": challenge_id,
        "attempts": n,
        "successes": successes,
        "trial_outcomes": {
            str(r["trial"]): bool(r.get("verified", False))
            for r in rows
        },
        "incidents": incidents,
        "complete": slots_complete and not incidents,
        "success_rate_pct": success_rate,
        "sample_sd_pp": (
            100 * stdev(outcomes)
            if slots_complete and n > 1 else None
        ),
        "mean_input_tokens": (
            mean_input if slots_complete else None
        ),
        "mean_output_tokens": (
            mean_output if slots_complete else None
        ),
        "mean_total_tokens": (
            mean_input + mean_output
            if slots_complete
            and mean_input is not None
            and mean_output is not None
            else None
        ),
        "mean_elapsed_s": (
            average(rows, "elapsed_s")
            if slots_complete else None
        ),

        "sample_variance": (
            variance(outcomes)
            if slots_complete and n > 1 else None
        ),
        "sample_variance_pp2": (
            10000 * variance(outcomes)
            if slots_complete and n > 1 else None
        ),

        # Pass@k estimates
        "pass_at_1_pct": (
            100 * pass_at_k(n, successes, 1)
            if slots_complete else None
        ),
        "pass_at_2_pct": (
            100 * pass_at_k(n, successes, 2)
            if slots_complete else None
        ),
        "pass_at_3_pct": (
            100 * pass_at_k(n, successes, 3)
            if slots_complete else None
        ),

        # Observed chronological first-k outcomes
        "observed_first_1_pct": (
            100 * int(any(outcomes[:1]))
            if slots_complete else None
        ),
        "observed_first_2_pct": (
            100 * int(any(outcomes[:2]))
            if slots_complete else None
        ),
        "observed_first_3_pct": (
            100 * int(any(outcomes[:3]))
            if slots_complete else None
        ),

        "total_elapsed_s": total(rows, "elapsed_s"),
        "mean_model_calls": average(rows, "model_calls"),
        "total_model_calls": total(rows, "model_calls"),
        "mean_model_attempts": average(rows, "model_attempts"),
        "total_model_attempts": total(rows, "model_attempts"),
        "mean_tool_calls": average(rows, "tool_calls"),
        "total_tool_calls": total(rows, "tool_calls"),

        # Known token usage, including failed attempts
        "known_total_input_tokens": total_input,
        "known_total_output_tokens": total_output,
        "known_total_tokens": (
            total_input + total_output
            if total_input is not None
            and total_output is not None
            else None
        ),

        # Missing cost is not zero cost
        "total_cost_usd": total(rows, "cost_usd"),

        # Incident accounting
        "incident_count": len(incidents),
        "status_counts": dict(Counter(
            r["status"] for r in rows
        )),
        "estimated_cost_usd": estimated_total_cost(rows),
    }

    return result


def write_csv(path, rows):
    if not rows:
        return

    columns = list(rows[0].keys())

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()

        for row in rows:
            clean = {
                key: (
                    json.dumps(value, sort_keys=True)
                    if isinstance(value, (dict, list))
                    else value
                )
                for key, value in row.items()
            }
            writer.writerow(clean)



def plot_pass_at_k(pass_rows):
    """Compare standard Pass@k estimates with ordered first-k outcomes."""
    ks = [row["k"] for row in pass_rows]
    estimated = [row["estimated_pass_at_k_pct"] for row in pass_rows]
    observed = [row["observed_first_k_pct"] for row in pass_rows]

    if any(value is None for value in estimated + observed):
        print("Skipping Pass@k plot: incomplete trial slots")
        return

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(ks, estimated, marker="o", linewidth=2,
            label="Estimated Pass@k")
    ax.plot(ks, observed, marker="s", linewidth=2,
            label="Observed success within first k trials")
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("Number of attempts (k)")
    ax.set_ylabel("Challenges solved (%)")
    ax.set_title("CTFTiny: Pass@k across 1–3 attempts")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.25)
    ax.legend(loc="upper left", fontsize=9)
    fig.text(0.5, 0.01,
             "Recorded attempts include model/tool incidents; estimates are descriptive.",
             ha="center", fontsize=8)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(PASS_PNG, dpi=200)
    plt.close(fig)


def summarize_trials(records, challenge_count):
    """Average binary solve outcome and sample variance across challenges, by trial."""
    rows = []
    for trial in sorted(EXPECTED_TRIALS):
        trial_records = [r for r in records if r["trial"] == trial]
        outcomes = [int(bool(r.get("verified", False))) for r in trial_records]
        full = len(trial_records) == challenge_count
        rows.append({
            "trial": trial,
            "challenges": len(trial_records),
            "average_solve_rate_pct": 100 * mean(outcomes) if full else None,
            "sample_variance": variance(outcomes) if full and len(outcomes) > 1 else None,
            "sample_sd_pp": 100 * stdev(outcomes) if full and len(outcomes) > 1 else None,
            "verified_successes": sum(outcomes),
        })
    return rows


def plot_solve_rate_variance(trial_rows):
    """Average solve rate by trial, with sample standard-deviation error bars."""
    if any(row["average_solve_rate_pct"] is None or
           row["sample_sd_pp"] is None for row in trial_rows):
        print("Skipping solve-rate plot: insufficient trial coverage")
        return

    trials = [row["trial"] for row in trial_rows]
    averages = [row["average_solve_rate_pct"] for row in trial_rows]
    deviations = [row["sample_sd_pp"] for row in trial_rows]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.bar(trials, averages, yerr=deviations, capsize=6)
    ax.set_xticks([1, 2, 3])
    ax.set_xlabel("Trial number")
    ax.set_ylabel("Average verified solve rate across challenges (%)")
    ax.set_title("CTFTiny: Average solve rate per trial and variability")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.25)
    fig.text(0.5, 0.01,
             "Error bars: sample SD across challenges (not a confidence interval).",
             ha="center", fontsize=8)
    fig.tight_layout(rect=[0, 0.05, 1, 1])
    fig.savefig(SOLVE_PNG, dpi=200)
    plt.close(fig)

def plot_per_challenge_solve_rate(summary_rows):
    labels = [r["challenge_id"] for r in summary_rows]
    rates = [r["success_rate_pct"] for r in summary_rows]

    fig, ax = plt.subplots(figsize=(8, 4.5))

    bars = ax.bar(labels, rates)

    ax.set_ylim(0, 100)
    ax.set_ylabel("Verified success rate (%)")
    ax.set_xlabel("CTFTiny challenge")
    ax.set_title("CTFTiny: Verified success rate by challenge")

    for bar, rate in zip(bars, rates):
        ax.annotate(
            f"{rate:.1f}%",
            (bar.get_x() + bar.get_width() / 2, rate),
            ha="center",
            va="bottom",
            xytext=(0, 5),
            textcoords="offset points",
        )

    fig.tight_layout()
    fig.savefig(
        BASE / "results" / "evaluation" / "per_challenge_solve_rate.png",
        dpi=200,
    )
    plt.close(fig)
    
# Assumed USD rates per million tokens for an illustrative cost estimate.
# Applied to known token counts only; this does not represent actual billed cost.
INPUT_PRICE_PER_MILLION = 0.15
OUTPUT_PRICE_PER_MILLION = 0.60


def estimate_cost(record):
    input_tokens = known_tokens(record, "input")
    output_tokens = known_tokens(record, "output")

    if input_tokens is None or output_tokens is None:
        return None

    return (
        input_tokens * INPUT_PRICE_PER_MILLION
        + output_tokens * OUTPUT_PRICE_PER_MILLION
    ) / 1_000_000


def estimated_total_cost(records):
    costs = [estimate_cost(record) for record in records]

    if any(cost is None for cost in costs):
        return None

    return round(sum(costs), 8)

def main():
    ids = [
        line.strip()
        for line in IDS_FILE.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    if not ids or len(ids) != len(set(ids)):
        raise ValueError("Invalid or duplicate challenge IDs")

    records = load_records()
    grouped = defaultdict(list)

    for record in records:
        if record.get("sample_type") != "live":
            raise ValueError(
                "Non-live record in official evaluation"
            )

        if record.get("config_id") != EXPECTED_CONFIG:
            raise ValueError("Unexpected configuration")

        challenge_id = record["challenge_id"]

        if challenge_id not in ids:
            raise ValueError(
                f"Unexpected challenge: {challenge_id}"
            )

        grouped[challenge_id].append(record)

    # Check frozen configuration and consistent budgets.
    for field in (
        "agent_version",
        "model_id",
        "benchmark_commit",
        "max_steps",
        "max_seconds",
    ):
        values = {r.get(field) for r in records}

        if len(values) != 1 or None in values:
            raise ValueError(
                f"Inconsistent evaluation setting: {field}"
            )

    summary = [
        summarize_challenge(challenge_id, grouped[challenge_id])
        for challenge_id in ids
    ]

    overall_complete = all(
        row["complete"] for row in summary
    )

    slots_complete = all(
        row["attempts"] == len(EXPECTED_TRIALS)
        and set(map(int, row["trial_outcomes"])) == EXPECTED_TRIALS
        for row in summary
    )

    total_successes = sum(r["successes"] for r in summary)
    total_attempts = sum(r["attempts"] for r in summary)

    # Pass@k is averaged equally across challenges.
    pass_rows = []

    for k in (1, 2, 3):
        estimated = [
            row[f"pass_at_{k}_pct"]
            for row in summary
        ]

        observed = [
            row[f"observed_first_{k}_pct"]
            for row in summary
        ]

        pass_rows.append({
            "k": k,
            "estimated_pass_at_k_pct": (
                mean(estimated)
                if all(v is not None for v in estimated)
                else None
            ),
            "observed_first_k_pct": (
                mean(observed)
                if all(v is not None for v in observed)
                else None
            ),
        })

    all_outcomes = [
        int(bool(r.get("verified", False)))
        for r in records
    ]

    total_input = token_total(records, "input")
    total_output = token_total(records, "output")
    trial_rows = summarize_trials(records, len(ids))

    output = {
        "benchmark": "CTFTiny",
        "config_id": EXPECTED_CONFIG,
        "agent_version": records[0]["agent_version"],
        "model_id": records[0]["model_id"],
        "benchmark_commit": records[0]["benchmark_commit"],
        "max_steps": records[0]["max_steps"],
        "max_seconds": records[0]["max_seconds"],

        "total_attempts": total_attempts,
        "total_successes": total_successes,
        "overall_complete": overall_complete,
        "observed_successes_per_attempt_pct": (
            100 * total_successes / total_attempts
            if total_attempts else None
        ),
        "overall_success_rate_pct": (
            100 * total_successes / total_attempts
            if overall_complete and slots_complete
            else None
        ),

        # Descriptive statistics for recorded attempts
        "observed_sample_sd_pp": (
            100 * stdev(all_outcomes)
            if len(all_outcomes) > 1 else None
        ),
        "observed_sample_variance": (
            variance(all_outcomes)
            if len(all_outcomes) > 1 else None
        ),

        # All recorded attempts, including failures
        "resources": {
            "total_elapsed_s": total(records, "elapsed_s"),
            "mean_elapsed_s": average(records, "elapsed_s"),
            "total_model_calls": total(records, "model_calls"),
            "mean_model_calls": average(records, "model_calls"),
            "total_model_attempts": total(
                records, "model_attempts"
            ),
            "mean_model_attempts": average(
                records, "model_attempts"
            ),
            "total_tool_calls": total(records, "tool_calls"),
            "mean_tool_calls": average(records, "tool_calls"),
            "known_input_tokens": total_input,
            "known_output_tokens": total_output,
            "known_total_tokens": (
                total_input + total_output
                if total_input is not None
                and total_output is not None
                else None
            ),
            "mean_known_input_tokens": token_average(
                records, "input"
            ),
            "mean_known_output_tokens": token_average(
                records, "output"
            ),
            "cost_usd": total(records, "cost_usd"),
            "estimated_cost_usd": estimated_total_cost(records),
        },

        "incident_counts": dict(Counter(
            r["status"]
            for r in records
            if r["status"] in INCIDENT_STATUSES
        )),
        "status_counts": dict(Counter(
            r["status"] for r in records
        )),
        "pass_at_k": pass_rows,
        "per_trial": trial_rows,
        "challenges": summary,

        "limitations": [
            "Infrastructure and scope incidents remain included "
            "in recorded attempt outcomes.",
            "The overall evaluation is incomplete when any "
            "incident remains unresolved.",
            "Known token counts may omit failed API requests "
            "without usage information.",
            "Null cost means unavailable, not zero.",
            "Pass@k estimates use recorded attempts and may "
            "be affected by infrastructure failures.",
            "Post-evaluation development pilots are excluded.",
        ],
    }

    attempt_rows = []

    for r in sorted(
        records,
        key=lambda x: (x["challenge_id"], x["trial"])
    ):
        input_tokens = known_tokens(r, "input")
        output_tokens = known_tokens(r, "output")

        attempt_rows.append({
            "challenge_id": r["challenge_id"],
            "trial": r["trial"],
            "run_id": r["run_id"],
            "status": r["status"],
            "verified": r.get("verified", False),
            "elapsed_s": r.get("elapsed_s"),
            "model_calls": r.get("model_calls"),
            "model_attempts": r.get("model_attempts"),
            "tool_calls": r.get("tool_calls"),
            "known_input_tokens": input_tokens,
            "known_output_tokens": output_tokens,
            "known_total_tokens": (
                input_tokens + output_tokens
                if input_tokens is not None
                and output_tokens is not None
                else None
            ),
            "cost_usd": r.get("cost_usd"),
            "trace_file": r.get("trace_file"),
            "estimated_cost_usd": (
                round(estimate_cost(r), 8)
                if estimate_cost(r) is not None
                else None
            ),
        })

    SUMMARY_JSON.write_text(
        json.dumps(output, indent=2) + "\n"
    )

    write_csv(SUMMARY_CSV, summary)
    write_csv(ATTEMPTS_CSV, attempt_rows)
    write_csv(PASS_CSV, pass_rows)
    write_csv(TRIAL_CSV, trial_rows)
    plot_pass_at_k(pass_rows)
    plot_solve_rate_variance(trial_rows)
    plot_per_challenge_solve_rate(summary)
    

    print(json.dumps(output, indent=2))

    print(
        "\nSaved summary.json, per_challenge.csv, "
        "per_attempt.csv, pass_at_k.csv, per_trial.csv, "
        "pass_at_k.png, solve_rate_variance.png, "
        "and per_challenge_solve_rate.png"
    )


if __name__ == "__main__":
    main()
