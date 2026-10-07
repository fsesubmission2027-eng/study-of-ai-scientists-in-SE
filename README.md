# AI Scientist Benchmark for Software Engineering Research

This repository is the anonymized replication package accompanying our submission.
It contains (1) the benchmark harness used to run end-to-end "AI Scientist" systems on
software-engineering research tasks inside Docker sandboxes, (2) the task
specifications derived from ICSE / FSE / ASE / ISSTA 2025 papers, (3) the multi-axis
evaluation pipeline, and (4) the aggregated evaluation results and per-run evaluation
reports reported in the paper.

---

## 1. Repository layout

```
.
├── README.md
├── benchmark_credentials.example.yaml   # template for API keys + per-framework model ids
├── orchestrator/        # Docker sandbox (TaskSandbox) and environment preflights
├── integrations/        # one launcher per AI Scientist framework + shared glue
│   ├── run_<framework>_task.py          # entry points (see §5)
│   ├── agent_task_document.py           # unified, blinded task prompt given to every agent
│   ├── metering_proxy.py, run_metering.py, model_pricing.yaml   # token / cost accounting
│   └── ...
├── evaluation/          # evaluation axes; entry point run_evaluate.py
├── docker/              # Dockerfiles for the agent sandbox images
├── benchmark/
│   ├── tasks/<TASK_ID>_<slug>/          # one directory per task (66 total)
│   │   ├── task.md                      # task given to the agent (blinded)
│   │   ├── task.env                     # sandbox image, resources, dataset mounts
│   │   ├── metadata.json                # source-paper metadata + structured task fields
│   │   ├── seeds/                       # starter files staged into the agent workspace
│   │   ├── evaluator/                   # task-level evaluator stub
│   │   ├── mineru_sections.json         # parsed sections of the source paper (alignment axis)
│   │   └── related_work.json            # related work of the source paper (idea novelty axis)
│   ├── selected_tasks.csv               # the 34 evaluated tasks
│   └── shared_datasets/                 # MANIFEST.csv + upstream READMEs (data not redistributed)
└── results/
    ├── summary/                         # aggregated results used in the paper
    │   ├── all_runs.csv                 # one row per (task, framework) run, all metrics
    │   ├── v2_summary.json, ts_data.json, abl_sig_v2.json
    │   └── analysis_scripts/            # scripts that produced the tables
    ├── evaluations/<task>/<run>/evaluation.json   # full per-run evaluation reports
    └── evaluations/<task>/*.json        # task-level references shared by all frameworks
```

## 2. Benchmark at a glance

| | |
|---|---|
| Candidate tasks | 66 (ASE 21, FSE 13, ICSE 23, ISSTA 9) |
| Evaluated tasks | 34 (listed in `benchmark/selected_tasks.csv`; 32 excluded by C1–C4 below) |
| Frameworks | 7: AI-Scientist-v2, AI-Researcher, ARIS, AutoResearchClaw, DeepScientist, EvoScientist, TinyScientist |
| Evaluated runs | 238 (34 tasks × 7 frameworks) |
| Evaluation axes | completeness, idea_generation, experiment_analysis, peer_review, alignment, literature_review |

Exclusion criteria for the 32 non-run tasks:

| Criterion | Meaning |
|---|---|
| **C1** | Non-substitutable hardware / overly complex environment |
| **C2** | Core dataset restricted or baseline not open-sourced |
| **C3** | Human subjects |
| **C4** | Task itself requires GPUs or additional LLM APIs |

## 3. Evaluation axes

| Axis | What is measured | Columns in `all_runs.csv` |
|---|---|---|
| completeness | Presence of the required artifacts (idea, code, substantive results, paper PDF/TeX) plus bonus artifacts (experiment plan, log, review, README, narrative, bib) | `comp_*`, `gate_*`, `paper_status`, `bonus_*` |
| idea_generation | LLM-judged novelty, feasibility and clarity of the idea (1–5), with novelty checked against the source paper's related work | `idea_*` |
| experiment_analysis | Whether experiments produced real results, idea–code consistency, coverage of the required datasets / baselines / metrics, ablation and significance testing, consistency between result files and the paper | `ea_*`, `abl2_*`, `sig2_*` |
| peer_review | Scores from an external automated reviewer (paperreview.ai) on the generated paper (1–10) | `pr_*`, `apr_*` |
| alignment | Agreement of the agent's claims and metrics with the claims extracted from the source paper | `al_*` |
| literature_review | Fabricated-reference rate (online verification), recall of the source paper's references, precision, recency | `lit_*` |

Aggregates: `fair_mean` averages the applicable axes; `strict4` counts missing axes as 0.
Cost columns: `tokens`, `llm_calls`, `cost_usd`, `duration_h` (from the metering proxy ledger).

`results/evaluations/<task>/` additionally holds three task-level files computed once and
shared by all seven frameworks, so that every framework is scored against the same reference:
`original_claims.json` (claims / metrics extracted from the source paper, used by alignment),
`solution_space.json` (related-work list used for idea novelty), and
`reference_verify_cache.json` (online verification results of cited references).

## 4. Inspecting the results (no setup required)

* Paper tables: `results/summary/all_runs.csv` (see §3 for the column groups).
* Per-run evidence: `results/evaluations/<task>/<run>/evaluation.json` contains every
  sub-score together with the LLM judge rationale and the relative paths of the artifacts
  that were used for scoring.

## 5. Re-running the benchmark

### 5.1 Requirements

* Linux host with Docker (Ubuntu 22.04 sandbox images; per-task CPU / memory limits are set
  in `task.env`, typically 8 CPUs / 32 GB)
* Python ≥ 3.10 with `pyyaml`, `requests` on the host
* An OpenAI-compatible LLM endpoint (we used `deepseek-v4-pro` for all frameworks;
  see `benchmark_credentials.example.yaml` for the exact per-framework model ids)
* Optional: Semantic Scholar API key (literature verification), Kaggle token (some tasks)

### 5.2 Installing the AI Scientist frameworks

The frameworks are **not** included in this repository. Install each one by following the
instructions in its official repository, at the version listed below. Each framework is used
**unmodified**; integration happens only through environment variables, CLI flags and
per-run config files written by `integrations/`.

| Framework | Official repository / package | Version used |
|---|---|---|
| AI-Scientist-v2 | https://github.com/SakanaAI/AI-Scientist-v2 | commit `96bd516` |
| AI-Researcher | https://github.com/HKUDS/AI-Researcher | commit `f9a6f84` |
| ARIS | https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep | commit `dd1ee32` |
| AutoResearchClaw | https://github.com/aiming-lab/AutoResearchClaw | commit `ea77ec1` |
| DeepScientist | https://github.com/ResearAI/DeepScientist | 1.6.0 (opencode 1.17.8) |
| EvoScientist | https://github.com/EvoScientist/EvoScientist | 0.1.7 |
| TinyScientist | https://github.com/ulab-uiuc/tiny-scientist | 0.1.3 |

Clone the git-based frameworks into the home directory (e.g. `~/AI-Scientist-v2`,
`~/Auto-claude-code-research-in-sleep`, `~/AutoResearchClaw`, `~/AI-Researcher`), which is
where the launchers look by default; see `--help` of each `run_*_task.py` for the flags /
environment variables that override these locations.

### 5.3 Setup

```bash
# 1. Place task specifications where the launchers expect them
mkdir -p ~/ai_scientist_inputs
cp -r benchmark/tasks/* ~/ai_scientist_inputs/

# 2. Obtain the shared datasets listed in benchmark/shared_datasets/MANIFEST.csv
#    (third-party artifacts, ~84 GB in total; each upstream README is included) and put them at
#    ~/ai_scientist_inputs/shared_datasets/<name>/   (path referenced by task.env EXTRA_VOLUME_*)

# 3. Build sandbox images
docker build -f docker/Dockerfile.base -t ai-scientist-base:20260615 docker/
docker build -f docker/Dockerfile.researchclaw-lite -t researchclaw/benchmark:latest docker/

# 4. Credentials
cp benchmark_credentials.example.yaml benchmark_credentials.yaml   # fill in keys
```

### 5.4 Running one task with one framework

```bash
TASK=~/ai_scientist_inputs/ASE-2025-004_predicting_recheck_success_in_continuous

python3 integrations/run_aris_task.py           --task-dir $TASK --launch
python3 integrations/run_researchclaw_task.py   --task-dir $TASK
python3 integrations/run_deepscientist_task.py  --task-dir $TASK
python3 integrations/run_evoscientist_task.py   --task-dir $TASK
python3 integrations/run_aiscientist_task.py    --task-dir $TASK
python3 integrations/run_tinyscientist_task.py  --task-dir $TASK
python3 integrations/run_airesearcher_task.py   --task-dir $TASK
```

Each run creates `$TASK/workspace/<framework>_<timestamp>/` containing the agent's
outputs, `artifacts/manifest.json`, and `artifacts/usage_ledger.jsonl` (all LLM calls
recorded by the metering proxy). Use `--help` on any launcher for resume / model options.

### 5.5 Evaluating a run

```bash
python3 evaluation/run_evaluate.py \
  --run-dir  $TASK/workspace/<framework>_<timestamp> \
  --task-dir $TASK \
  --axes all            # or e.g. completeness,alignment
# -> ~/ai_scientist_evals/<task>/<run>/evaluation.json
```

`--skip-llm` runs only the rule-based checks; `--skip-verify` disables online
reference verification.

To reuse the released task-level references instead of re-extracting them with an LLM,
copy them first and point `--evals-root` at the copy (reports are written there as well):
`cp -r results/evaluations /tmp/evals`.

## 6. Notes

* **Task blinding.** Task IDs and venue/year strings are stripped from the prompt
  (`integrations/task_prompt.py`) so agents cannot trivially retrieve the source paper.
* **Source papers.** `metadata.json` and `mineru_sections.json` contain excerpts of the
  published source papers, used only as the reference for evaluation.
* **Third-party data.** Datasets under `shared_datasets/` belong to their original authors
  and are not redistributed here; see each upstream README for licence and download.
