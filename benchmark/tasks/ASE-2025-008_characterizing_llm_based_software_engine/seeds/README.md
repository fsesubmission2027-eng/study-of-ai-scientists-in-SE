# Seeds for ASE-2025-008 — LLM Agent Trajectory Analysis

## Downloaded data

The replication package has already been cloned:

- repository: `https://github.com/sola-st/llm-agents-study`
- pinned/current commit: `e84f66f8d494e46ef336edfa137db25a629614fb`
- host path: `~/ai_scientist_inputs/shared_datasets/llm-agents-study`
- legacy Docker mount: `/shared/llm-agents-study` (read-only)
- AI Scientist path: `dataset_candidate/llm-agents-study/`
- environment variable: `LLM_AGENTS_STUDY_HOME=dataset_candidate/llm-agents-study`

The repository contains annotated CSVs for AutoCodeRover, OpenHands/CodeActAgent,
and RepairAgent, as well as the authors' `stats/` analysis scripts.

## Python environment

Do not create or activate a virtual environment inside the shared repository.
`container_setup.sh` automatically creates a disposable environment at:

```text
/opt/ase-2025-008-venv
```

It installs the repository requirements (`matplotlib`, `matplotlib-venn`,
`numpy`, and `pandas`). `task.env` puts this environment first on `PATH`, so
inside the task container both commands below use the prepared environment:

```bash
python --version
python -c "import matplotlib, matplotlib_venn, numpy, pandas"
```

Therefore these host-side commands are not required:

```bash
cd llm-agents-study
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

A host `.venv` is not portable into the task container because its interpreter
paths are tied to the host clone location.

## Running analyses

The mounted package is deliberately read-only so every framework sees the same
unchanged inputs. Some author scripts write figures and sequence files beneath
the repository, so copy it into the run workspace first:

```bash
cp -a "$LLM_AGENTS_STUDY_HOME" project/llm-agents-study
cd project/llm-agents-study
python stats/actions_bars.py
python stats/top_sequences.py
```

For read-only custom analysis, scripts may read `$LLM_AGENTS_STUDY_HOME`
directly and write results under `project/` or `artifacts/`.

## Agent-visible files

- `agent/dataset_paths.json`: concrete paths, layout, commit, and copy policy.
- `agent/metrics.json`: required and optional metric keys.
- `benchmark_config.json`, `README.md`, and `container_setup.sh` are
  orchestration/human documentation and are not staged as dataset inputs.
