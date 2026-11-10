# Autonomous CTF Agent — Benchmarking Assignment

Duke University · Final Project, Part 1 · November 11, 2026

## Overview

This project implements an autonomous, multi-step CTF-solving agent using the Ollama Cloud chat API (`gpt-oss:120b`). An agent loop selects tools, observes their outputs, and adapts subsequent actions. A trusted Python controller manages tool dispatch, isolated execution, candidate-flag verification, resource budgets, and JSONL trace logging. The solver does **not** receive the benchmark answer key.

This repository contains two distinct agent versions: the frozen configuration used for the nine reported evaluation attempts and a post-evaluation development configuration. Do not conflate their results.

## Evaluated benchmark and configuration

| Setting | Frozen evaluation |
|---|---|
| Benchmark | [NYU CTFTiny](https://github.com/NYU-LLM-CTF/CTFTiny) |
| CTFTiny source commit | `f1c9531672c45b24b7fb5f3aa44a7ac33d3602f8` |
| Selected challenges | `rev-checker`, `rev-baby-mult`, `rev-whataxor` (also in `evaluation_ids.txt`) |
| Attempts | Three independent attempts per selected challenge; nine records total |
| Model | `gpt-oss:120b` via Ollama Cloud, `https://ollama.com/api/chat` |
| Solver budget | 15 tool steps and 300 seconds per attempt |
| Agent commit used for evaluation | `7a39bf0f4e86c266b4475323e61ca9ad3aa5edd3` |
| Configuration ID in records | `agent` |

The current code includes post-evaluation improvements: targeted binary inspection, bounded disassembly, more efficient tool guidance, and recovery from unknown tool names, all initially committed at `8acbb26`. A later dependency-lock commit was `83356be`. Use `git rev-parse HEAD` to identify the precise current development configuration; **it was not evaluated in a second full nine-run benchmark**.

## Prerequisites and clean setup

- Git, Docker with a working daemon, and Python compatible with `requirements.lock.txt` (the project was developed in GitHub Codespaces).
- Access to the Ollama Cloud API and an `OLLAMA_API_KEY` environment variable. A local Ollama server is **not** used.
- The external CTFTiny and NYU CTF Bench datasets in the exact paths expected by `challenge_runner.py`.

From a clean clone of this repository:

```bash
git clone https://github.com/tsuyuuu/ml-ctf-agent.git
cd ml-ctf-agent
python -m venv .venv
.venv/bin/python -m pip install -r requirements.lock.txt

mkdir -p external
git clone https://github.com/NYU-LLM-CTF/CTFTiny.git external/CTFTiny
git -C external/CTFTiny checkout f1c9531672c45b24b7fb5f3aa44a7ac33d3602f8

git clone https://github.com/NYU-LLM-CTF/NYU_CTF_Bench.git external/NYU_CTF_Bench
# For exact development-dataset reproduction, use the separately recorded
# NYU_CTF_Bench revision from the original development environment.

test -f external/CTFTiny/ctftiny.json
test -f external/NYU_CTF_Bench/development_dataset.json

docker build -f Dockerfile.solver -t ctf-solver:dev .
export OLLAMA_API_KEY='YOUR_OLLAMA_CLOUD_KEY'
```

Keep the API key out of commits, terminal recordings, log output, and shared artifacts. The `nyuctf` Python package is used to load dataset metadata and contestant files; it is installed through the project lockfile.

**Important:** We have verified the public benchmark clone URLs, but the complete fresh-install sequence above has **not** been independently executed on a new machine for this README. Check package installation, Docker permissions, and exact external benchmark availability before asserting clean-machine reproducibility.

## Commands and intended use

The current repository uses these commands:

```bash
# Validate selected CTFTiny challenges without model calls:
.venv/bin/python benchmark_runner.py --mode evaluation --check

# Run a development pilot (appends to development records):
.venv/bin/python benchmark_runner.py --mode pilot --challenge-id rev-checker

# Run official evaluation attempts (DO NOT run over submitted evidence):
.venv/bin/python benchmark_runner.py --mode evaluation

# Regenerate aggregates, CSVs, and plots from existing official records:
.venv/bin/python summarize_results.py
```

The official evaluation command performs three attempts per selected challenge and avoids existing trial slots. To independently reproduce the original nine-run evaluation, use a separate clean working directory checked out at the original evaluated commit `7a39bf0f4e86c266b4475323e61ca9ad3aa5edd3`, install its dependencies and benchmark checkout, and run there with a new result file. Do not copy or overwrite submitted `results.jsonl` or traces. The frozen commit predates the current `results/` directory reorganization, so read its README and script paths from that checkout rather than assuming today's paths were present then. An independent replay involves fresh model calls and can yield different outcomes.

## Results and artifacts

Current post-reorganization output layout:

```text
results/
  evaluation/
    results.jsonl                 # original nine official attempt records
    summary.json                  # aggregate metrics and limitations
    per_challenge.csv             # metrics for each of three challenges
    per_attempt.csv               # time, calls, tokens, outcome per attempt
    per_trial.csv                 # average solve rate and sample variance by trial
    pass_at_k.csv                 # estimated Pass@1/2/3 and observed first-k
    pass_at_k.png                 # Pass@k plot
    solve_rate_variance.png       # per-trial mean solve rate with sample SD bars
    per_challenge_solve_rate.png  # supplementary challenge-level plot, if generated
  development/
    ctftiny_pilot_results.jsonl   # development-only pilots; not scored
logs/                              # execution traces, where retained
 evidence/                         # isolation tests and development examples
```

Some archived development traces may instead live under `evidence/development/`. Each record has a `run_id` and `trace_file`; retained traces should be cross-checked against the corresponding ID if files were moved. Trace paths in JSONL may be absolute paths from the original Codespaces environment and are not automatically portable.

### Recorded results (frozen evaluation only)

| Challenge | Verified successes | Recorded attempts | Observed successes/attempts |
|---|---:|---:|---:|
| `rev-checker` | 1 | 3 | 33.33% |
| `rev-baby-mult` | 0 | 3 | 0% |
| `rev-whataxor` | 0 | 3 | 0% |
| **Total** | **1** | **9** | **11.11% observed** |

`overall_complete` is *false* because four attempts ended with model API errors and one ended with a recorded `scope_violation`. The latter was traced to an unsupported tool name, not a demonstrated escape from the container. The remaining three attempts were budget-exhausted. Do not present 11.11% as an incident-free, completed benchmark success rate.

From `summary.json`, the nine attempts used 117.45 seconds of recorded wall-clock time, 62 model calls, 77 model API attempts including retries, 62 tool calls, 230,673 known input tokens, and 7,136 known output tokens. The 237,809 total known tokens may undercount failed API requests without usage data. Pass@1/2/3 estimates are 11.11%, 22.22%, and 33.33%, calculated from the recorded binary outcomes; these estimates are affected by the incomplete runs.

Monetary `cost_usd` was not provided by the API. The aggregation script separately calculates a rate-based estimate on known tokens using its documented price assumptions; it is not an observed charge and excludes unknown consumption from failed requests. Refer to the generated summary for the value and rate assumptions applicable at report generation time.

## Architecture, tools, and control boundary

- `agent_core.py`: iterative Ollama tool-call loop, observation handling, bounded execution, retries, usage tracking, traces.
- `tools.json`: available tool names, descriptions, and argument schemas.
- `controller.py`: `ToolDispatcher` validates and dispatches requests and passes candidate flags to the verifier.
- `ctf_tools.py`: development-only specialized binary inspection and bounded disassembly functions (present in the improved configuration).
- `solver_runtime.py`: runs shell operations in a restricted Docker container; controls per-command timeouts and cleanup.
- `challenge_runner.py`: loads the selected dataset and copies contestant-visible files into a temporary directory.
- `flag_verifier.py`: private candidate verification; expected flags remain in trusted controller memory.
- `benchmark_runner.py`: preflight, fresh per-attempt workspace/container, trial bookkeeping, and result recording.
- `summarize_results.py`: post-hoc metrics and plots; never needs an Ollama request.

The solver runs as an unprivileged user with `--network none`, read-only root filesystem, a read-only `/challenge` mount, writable `/work` tmpfs, dropped capabilities, limited processes/memory/CPU, and per-command timeouts. The Docker socket and full benchmark repository are not mounted into the solver. `preflight()` checks selected files and rejects challenges requiring a separate service/Compose target. These settings are appropriate for the three selected file-based challenges, not a general guarantee of network-challenge compatibility.

**Limitations:** `run_command` permits general shell commands *within the isolated container* and is not a complete command-level path allowlist. `_safe_path()` validates path strings for dedicated file tools but does not provide comprehensive resolved-path confinement. Unexpected exceptions may prevent a trial record from being appended despite container cleanup. These are documented limitations, not claims of fully prevented behavior.

## Improvement testing and selected competition configuration

The original `rev-whataxor` evaluation exposed invalid tool selection and excessive disassembly output. In a post-evaluation pilot, the model requested nonexistent tool `objdump`, leading to premature termination. We then changed unknown-tool requests into recoverable tool errors; an offline mocked-response test showed the agent recovering and finishing. Dedicated dispatcher tests of binary inspection, bounded disassembly, and blocked paths also passed.

A later development pilot of `rev-checker` (run `4d3125ab-328d-4dc8-801e-38e04a55ff2a`) produced a verified flag in five tool calls. This is separate from the official nine evaluation attempts. These tests validate components and show a successful pilot, but do not establish an improved benchmark solve rate. The current improved agent is the intended candidate for continued development for the competition on November 18th, subject to regression testing.

## Demonstration and reporting

We have produced and added a report (Assignment4Report.pdf) totaling our current findings, and future plans for implementation/improvement. We also recorded a video going through a run, and explaining how it works.

## Reused sources and AI disclosure

Benchmark source: [NYU-LLM-CTF/CTFTiny](https://github.com/NYU-LLM-CTF/CTFTiny). Dataset loader and related tooling: [NYU-LLM-CTF/NYU_CTF_Bench](https://github.com/NYU-LLM-CTF/NYU_CTF_Bench). Ollama Cloud provides model inference.

AI assistance was used for implementation guidance, debugging, test design, and documentation. The places AI was used are cited in the code itself. AI was not used without human intervention, and all outputs were carefully looked at before being used. No whole section was done through AI, only small pieces.
