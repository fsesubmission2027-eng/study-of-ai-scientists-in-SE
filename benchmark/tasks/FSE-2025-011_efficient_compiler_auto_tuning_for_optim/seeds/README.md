# Seeds for FSE-2025-011 — PDCAT Compiler Auto-Tuning

## Downloaded data

The paper artifact is cloned on the host:

- repository: `https://github.com/zhumxxx/PDCAT-master.git`
- stub redirect: `https://github.com/fse2025any/PDCAT` (points to the repo above)
- host path: `~/ai_scientist_inputs/shared_datasets/pdcat-master`
- legacy Docker mount: `/shared/pdcat-master` (read-only)
- AI Scientist / aligned path: `dataset_candidate/pdcat-master/`
- environment variable: `PDCAT_HOME=dataset_candidate/pdcat-master`

### What is inside (~35 MB total)

| Path | Content |
|------|---------|
| `Benchmarks/cBench/` | **28** cBench C programs + input data |
| `Benchmarks/polyBench/` | **30** PolyBench computational kernels |
| `Algorithm/overall/` | PDCAT, RIO, CFSCA, CompTuner, SRTuner reference implementations |
| `Algorithm/ablation/` | Ablation-study variants |
| `Results/` | Author precomputed experiment tables |

Re-download / verify:

```bash
./download_pdcat_dataset.sh
```

No Git LFS required. Clone is small (~35 MB); compute cost dominates (compile + execute loops).

## Docker / toolchain environment

`container_setup.sh` automatically creates:

```text
/opt/fse-2025-011-venv
```

It installs `build-essential`, `gcc`, `g++`, `make`, `time`, and Python scientific stack.
`task.env` puts the venv first on `PATH`.

**GCC version note:** the paper uses **GCC 13.1.0**; the base image ships Ubuntu 22.04 / gcc 11.4
(container_setup tries gcc-12 when available). Author scripts accept `--gcc_path=gcc`.

## Agent-visible files

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Benchmark paths and program counts |
| `agent/metrics.json` | Yes | Required metric keys |
| `requirements.txt` | No (pip only) | Python deps for orchestration |
| `container_setup.sh` | No (root setup) | GCC/Python install |
| `benchmark_config.json` | No | Staging / benchmark rules |
| `README.md` | No | Human documentation |

## Scale note

Full paper reproduction: 58 programs × 4 baselines × 3 time budgets × 5 repeats,
each repeat compiling and executing many flag sequences — **days of CPU time**.

Benchmark runs should use subset sampling and/or reduced time budgets when documented;
the **full benchmark sources** remain available under `dataset_candidate/pdcat-master/Benchmarks/`.
