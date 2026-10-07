# Seeds for ISSTA-2025-005 — DFA-GNN (algorithmic alignment with data-flow analysis)

## Agent data policy

Use the mounted ProGraML CFG graphs and DFAGNNs sources. Agent inputs must
follow the task protocol; do not inject reduced-budget or substitute-evaluation
guidance.

## Quick start (host)

```bash
cd ~/ai_scientist_inputs/ISSTA-2025-005_algorithmic_alignment_of_graph_neural_ne
chmod +x download_dfagnns_dataset.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh \
  seeds/container_setup.sh
./download_dfagnns_dataset.sh
./run_aiscientist_benchmark.sh run
```

Docker uses `ai-scientist-base:20260615` (`task.env`: `MEMORY=32g`, `CPUS=8`,
`CONTAINER_SETUP=true`). On start, `seeds/container_setup.sh` installs a CPU
JAX/Haiku stack into `/opt/issta-2025-005-venv` and editable-copies DFAGNNs.

## How to download / sizes

| Item | Value |
|------|-------|
| Host path | `~/ai_scientist_inputs/shared_datasets/dfagnns-issta2025` |
| In-container | `/shared/dfagnns-issta2025` |
| Agent path | `dataset_candidate/dfagnns-issta2025/` |
| DFAGNNs code | https://github.com/yizhidou/DFAGNNs (~9 MiB git) |
| programl_edited | https://github.com/yizhidou/programl_edited (~47 MiB git) |
| ProGraML graphs archive | `graphs_20.06.01.tar.bz2` from Zenodo DOI [10.5281/zenodo.4247595](https://doi.org/10.5281/zenodo.4247595) |
| Archive download size | **≈ 3.5 GiB** (3,756,644,236 bytes) |
| Full uncompressed graphs | **≈ 67 GiB** |
| Default extract (`EXTRACT_MODE=task_bins`) | POJ-104 bins matching task.md: 0–50 / 500–600 / 600–700 / 900–1000 (**34,712** samples in statistics) |

Commands:

```bash
# default: clone repos + download archive + extract POJ-104 task bins
./download_dfagnns_dataset.sh

# keep archive only (no extract)
EXTRACT_MODE=archive_only ./download_dfagnns_dataset.sh

# extract entire ProGraML graphs (~67 GiB free space required)
EXTRACT_MODE=full ./download_dfagnns_dataset.sh
```

Layout after download:

```text
$DFAGNNS_HOME/
  DFAGNNs/                 # paper code (clrs/_src/dfa/...)
  programl_edited/         # yzd_analyze sources (Bazel build needed)
  graphs/                  # *.ProgramGraph.pb CFGs
  statistics/              # poj104_full_statistics.json etc.
  archives/graphs_20.06.01.tar.bz2
  DOWNLOAD_META.txt
```

## Not included (runtime / build)

| Component | Notes |
|-----------|--------|
| Built `programl.yzd_analyze` binary | Requires Bazel build of `programl_edited` |
| Full ProGraML llvm_ir / all label tarballs | Paper uses CFGs; labels/trajectories are generated |
| CUDA JAX | CPU jaxlib is preinstalled; install CUDA build in `project/` if GPU present |

## Layout (seeds/)

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Mount paths / size notes |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | JAX/Haiku stack |
| `container_setup.sh` | No | Root one-shot Python install |
| `benchmark_config.json` | No | Staging rules |
| `README.md` | No | Human documentation |
