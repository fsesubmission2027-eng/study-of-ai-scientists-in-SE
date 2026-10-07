# Seeds for ICSE-2025-023 — npm Dependency Abandonment (Zenodo AE)

## Agent data policy

Use the **Zenodo replication package** via the shared mount
(`NPM_ABANDONMENT_HOME=/shared/npm-dependency-abandonment-icse2025` inside Docker;
agent path `dataset_candidate/npm-dependency-abandonment-icse2025/`).

Prefer re-running `explorationAndModeling.Rmd` (or Python reanalysis of `data/*.csv`)
over remine of npm / World of Code / OSV inside the sandbox.

Human-only files live in `seeds/` root. Agent-visible config is under `seeds/agent/` only.

## Quick start (host)

```bash
cd ~/ai_scientist_inputs/ICSE-2025-023_investigating_dependency_abandonment_and
chmod +x download_npm_abandonment.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh \
  seeds/container_setup.sh
./download_npm_abandonment.sh
./run_aiscientist_benchmark.sh run
```

Docker uses `ai-scientist-base:20260615` (`task.env`: `MEMORY=32g`, `CPUS=8`,
`CONTAINER_SETUP=true`). On start, `seeds/container_setup.sh` installs R (paper Rmd
stack) + Python (`lifelines`/`statsmodels`) into `/opt/icse-2025-023-venv`.

## Dataset (Zenodo AE)

| Item | Value |
|------|-------|
| Host path | `~/ai_scientist_inputs/shared_datasets/npm-dependency-abandonment-icse2025` |
| In-container | `/shared/npm-dependency-abandonment-icse2025` |
| Agent path | `dataset_candidate/npm-dependency-abandonment-icse2025/` |
| Zenodo zip | **≈ 1.56 MiB** (`replicaitonPackage.zip`, 1639524 bytes, md5 `53aa6c058a35bb82e68aa4144761c59e`) |
| Extracted tree | **≈ 5–7 MiB** (with zip kept) |
| DOI | https://doi.org/10.5281/zenodo.13323422 |

Layout:

```text
$NPM_ABANDONMENT_HOME/
  data/
    widelyUsednpmPackages.csv              # ~28,100 packages
    abandonmentExposedDependentsData.csv   # ~2,288 dependents
    updateExposedDependentsData.csv        # ~11,925 (RQ2b baseline)
    vulnerabilityExposedDependentsData.csv # ~13,190 (RQ2c baseline)
  explorationAndModeling.Rmd
  visualizations/
  README.md
```

## Layout (seeds/)

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Mount paths / CSV sizes |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | Python analysis deps |
| `container_setup.sh` | No | Root one-shot R+Python install |
| `benchmark_config.json` | No | Staging rules |
| `README.md` | No | Human documentation |

## Notes

- Upstream zip filename is intentionally misspelled `replicaitonPackage.zip`.
- Sandbox path is AE CSV reanalysis; full ecosystem remine is out of scope.
