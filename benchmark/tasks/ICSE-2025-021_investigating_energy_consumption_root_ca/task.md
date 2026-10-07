# Task: ICSE-2025-021 — Investigating Energy Consumption Root Causes in Docker Base Images for Server Applications

## Background

The growing energy demand of data centers makes server-side energy efficiency critical, yet it remains underexplored compared to mobile computing. One important but overlooked factor is the Linux distribution chosen as a base image for containerized applications; image size is prioritized while energy impact is ignored. Recent work has shown that different base images can lead to significantly different energy consumption for the same application, but no systematic approach exists to trace these differences to their root software causes. This gap leaves developers without the means to identify and fix energy regressions hidden in operating system components or standard libraries.

## Research Question

How can developers systematically locate the root causes of energy consumption regressions that arise from running the same application on different Linux distribution base images?

## Experiment Setup

### Datasets
```
- name: EnergyDebug AE artifact (Redis / PostgreSQL / memcpy energy + traces)
  source: Zenodo https://doi.org/10.5281/zenodo.14856317 (concept https://doi.org/10.5281/zenodo.14718382); GitHub https://github.com/enriquebarba97/EnergyDebug
  description: Pre-collected EnergiBridge energy CSVs, docker-compose logs, and uftrace dumps for Redis, PostgreSQL, and memcpy microbenchmarks across Alpine/musl vs Ubuntu/glibc style configurations, plus energydebug.ipynb for log-alignment and hotspot localization. Zenodo EnergyDebug.zip ≈ 2.29 GiB (~2.5 GB).
  access: provided via shared_datasets/energydebug-icse2025 (download_energydebug.sh)
```

### Baselines
```
- name: Macroscopic energy comparison (Tjiong et al.)
  reference: J. Tjiong et al., ‘The Impact of Docker Base Images on Energy Consumption’ (prior work, year unknown)
```

### Metrics
```
- name: Total energy consumption
  definition: Energy used by the CPU core during the benchmark workload, measured in Joules using EnergiBridge.
- name: Average power
  definition: Average power drawn by the core during execution, in Watts.
- name: Execution time
  definition: Wall-clock time for the benchmark to complete, in seconds.
```

### Sub-questions
```
- RQ1: To what extent does the energy consumption of an in-memory database differ when run on Alpine vs Ubuntu base images, after controlling for software version, compiler, and memory allocator?
- RQ2: Can a systematic investigation identify which specific software component (e.g., a shared library function) is responsible for any observed energy difference?
- RQ3: Can the suspected component be isolated and benchmarked independently to confirm it as the primary cause of the energy regression?
```

### Target Subject

Containerized server applications using Linux distribution base images; for the case study, Redis, an in-memory key-value store, running on Alpine (musl) and Ubuntu (glibc) variants. Other examples could include Nginx or PostgreSQL.

### Constraints

Experiments must be run on bare-metal hardware with a modern AMD or Intel CPU supporting core-level energy counters. The workload must be pinned to a single core while all other processes are confined to other cores. CPU frequency and voltage must be fixed. A CPU warm-up phase of 6 minutes must precede every measurement. For each configuration, 30 independent runs must be performed in randomized order with short pauses in between. Energy measurement must be carried out with a tool like EnergiBridge (available on GitHub) that reports per-core energy at regular intervals. Compiler version (GCC 12.3), Redis version (7.2.4), and benchmark parameters (50 clients, 100000 requests) must be identical across all configurations.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The AE artifact provides pre-collected energy/trace data and `energydebug.ipynb` for analysis reproduction without bare-metal MSR access. New EnergiBridge collection still needs AMD/Intel energy counters, single-core pinning, 6-minute warm-up, and 30 randomized repeats (paper host: Ryzen 9 7900X). For AI-Scientist sandbox runs, prefer re-analysis of the mounted artifact (or disclosed reduced subsets) rather than inventing synthetic energy traces. Redis / Dockerfiles / EnergiBridge remain available if privileged measurement hardware is present.

### Harness (AI Scientist / container)

Wired like ICSE-2025-019 (**paper AE artifact** + container Python analysis stack):

| File | Role |
|------|------|
| `download_energydebug.sh` | Host-side download from Zenodo (`EnergyDebug.zip` ≈ **2.29 GiB / ~2.5 GB**) |
| `task.env` | Docker image, `MEMORY=32g`, `CPUS=8`, mount `shared_datasets/energydebug-icse2025` |
| `seeds/container_setup.sh` | numpy/pandas/scipy/statsmodels/seaborn + jupyter/nbconvert |
| `run_aiscientist_benchmark.sh` / `run_airesearcher_benchmark.sh` | Launchers |

```bash
chmod +x download_energydebug.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh
./download_energydebug.sh
./run_aiscientist_benchmark.sh run
```

**Zenodo:** https://doi.org/10.5281/zenodo.14856317  
**GitHub:** https://github.com/enriquebarba97/EnergyDebug  
**Shared data root:** `~/ai_scientist_inputs/shared_datasets/energydebug-icse2025`  
**In-container mount:** `/shared/energydebug-icse2025` → agent `dataset_candidate/energydebug-icse2025/`

### Dataset size

| Item | Size / note |
|------|-------------|
| Zenodo `EnergyDebug.zip` | **≈ 2.29 GiB（约 2.5 GB）**，md5 `5130b1717d323b6cc3f28daefef6f126` |
| Extracted tree | See `.artifact_meta.txt` / `du -sh`（energy + uftrace，通常数 GB） |
| Subjects | Redis, PostgreSQL, memcpy |
| Paper headline deltas | up to **~20.2%** power / **~8.6%** energy (Alpine/musl vs Ubuntu/glibc after controls) |

## Metadata

```
subfield: Software Maintenance & Evolution
venue: ICSE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```