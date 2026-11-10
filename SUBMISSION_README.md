# Autonomous CTF Agent — Benchmarking Assignment

## Overview
An autonomous CTF-solving agent using Ollama Cloud and a Docker-isolated
solver. The trusted Python controller manages tool execution, verification,
resource limits, logging, and environment resets.

## Benchmark
- Dataset: NYU CTFTiny
- Benchmark commit: f1c9531672c45b24b7fb5f3aa44a7ac33d3602f8
- Challenge IDs: evaluation_ids.txt
- Attempts: 3 per challenge
- Model: gpt-oss:120b
- API: https://ollama.com/api/chat
- Limits: 15 tool steps and 300 seconds per attempt

## Reproducibility
Original evaluated configuration:
7a39bf0f4e86c266b4475323e61ca9ad3aa5edd3

Improved post-evaluation configuration:
8acbb26

Python dependencies:
requirements.lock.txt

The evaluated configuration must be used when reproducing the nine
reported benchmark attempts. The improved configuration has not
undergone a second full evaluation.

## Setup
Requires Python, Docker, the CTFTiny benchmark checkout, and an
Ollama Cloud API key.

Install dependencies:
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt

Set OLLAMA_API_KEY in the environment. Never commit this secret.

Build the solver image:
docker build -f Dockerfile.solver -t ctf-solver:dev .

## Commands
Check challenge compatibility:
.venv/bin/python benchmark_runner.py --mode evaluation --check

Run three attempts per selected challenge:
.venv/bin/python benchmark_runner.py --mode evaluation

Summarize existing results:
.venv/bin/python summarize_results.py

Note: the benchmark runner skips existing evaluation slots; use a
clean results directory or checkout for an independent reproduction.
Do not overwrite the submitted evaluation evidence.

## Results
Official results: results.jsonl
Summary: summary.json
Per-challenge statistics: per_challenge.csv
Execution traces: logs/

Observed: 1 verified solve in 9 attempts.
Four model errors and one unsupported-tool termination affected the
evaluation. Results are therefore marked incomplete for reporting.

## Safety and isolation
The solver runs in a non-root Docker container without network access.
Only contestant files are mounted, read-only. Expected flags and
benchmark answer metadata remain in the trusted controller.

## Development changes
Following trace inspection, we added binary inspection, bounded
disassembly, improved tool guidance, and recovery from unknown tool
requests. Offline integration tests passed. An improved solve rate
has not been established.

## Disclosure
AI assistance was used for implementation guidance, debugging,
testing, and documentation. Team contributions and additional
attribution are documented in the accompanying report.
