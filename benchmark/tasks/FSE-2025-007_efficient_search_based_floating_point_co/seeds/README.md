# Seeds for FSE-2025-007 — QSF Floating-Point Constraint Solving

## Downloaded data

The paper artifact is cloned and benchmarks extracted on the host:

- repository: `https://github.com/zbchen/QSF.git`
- host path: `~/ai_scientist_inputs/shared_datasets/qsf`
- legacy Docker mount: `/shared/qsf` (read-only)
- AI Scientist / aligned path: `dataset_candidate/qsf/`
- environment variable: `QSF_HOME=dataset_candidate/qsf`

### Benchmark files (agent must use these)

| Path | Content |
|------|---------|
| `data/benchmarks/smtlib_qf_fp/` | **266** QF_FP SMT-LIB2 instances (SMT-COMP 2023 subset) |
| `data/benchmarks/program_qf_fp/` | **3493** real-world program constraints (GSL/KLEE) |
| `smt-runner/` | Author experiment runner scripts (optional reference) |
| `data/experiments/` | Author pre-computed results (optional reference) |

Re-download / verify:

```bash
./download_qsf_dataset.sh
```

Requires `git-lfs`. The download script pulls LFS archives (~93 MB compressed) and
extracts them in place (~8.5 GB total on disk for full extracted benchmarks).

## Python / toolchain environment

`container_setup.sh` automatically creates:

```text
/opt/fse-2025-007-venv
```

It installs `z3`, `clang`, `llvm`, `cmake`, and Python scientific stack.
`task.env` puts the venv first on `PATH`.

**Baseline solvers are intentionally not preinstalled.** The agent may install
comparison tools (e.g. `z3` CLI already present) or implement its own baselines.

## Agent-visible files

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Benchmark paths and instance counts |
| `agent/metrics.json` | Yes | Required metric keys |
| `requirements.txt` | No (pip only) | Python deps for orchestration |
| `container_setup.sh` | No (root setup) | Z3/LLVM/Python install |
| `benchmark_config.json` | No | Staging / benchmark rules |
| `README.md` | No | Human documentation |

## Scale note

Full benchmark evaluation against nine paper baselines with 60s/600s timeouts and
10 repeats is far beyond a single autonomous run. Subset sampling and shorter
timeouts are acceptable when documented; the **full benchmark files** remain
available under `dataset_candidate/qsf/data/benchmarks/`.
