# Seeds for ISSTA-2025-001 — GzFuzz (Gazebo robotic simulator fuzzing)

## Agent data policy

Use the **GzFuzz replication package** via the shared mount
(`GZFUZZ_HOME=/shared/gzfuzz-issta2025` inside Docker;
agent path `dataset_candidate/gzfuzz-issta2025/`).

Mounted inputs include `data/` (campaign logs / crashes / coverage artifacts)
and `src/`. Agent inputs must follow the task protocol; do not inject
reduced-budget or substitute-evaluation guidance.

Human-only files live in `seeds/` root. Agent-visible config is under `seeds/agent/` only.

## Quick start (host)

```bash
cd ~/ai_scientist_inputs/ISSTA-2025-001_fuzz_testing_for_robotic_simulation_plat
chmod +x download_gzfuzz.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh \
  seeds/container_setup.sh
./download_gzfuzz.sh
./run_aiscientist_benchmark.sh run
```

Docker uses `ai-scientist-base:20260615` (`task.env`: `MEMORY=32g`, `CPUS=8`,
`CONTAINER_SETUP=true`). On start, `seeds/container_setup.sh` installs CPU torch +
paper Python deps into `/opt/issta-2025-001-venv`.

## Dataset (GzFuzz GitHub AE)

| Item | Value |
|------|-------|
| Host path | `~/ai_scientist_inputs/shared_datasets/gzfuzz-issta2025` |
| In-container | `/shared/gzfuzz-issta2025` |
| Agent path | `dataset_candidate/gzfuzz-issta2025/` |
| GitHub | https://github.com/liyitao-code/GzFuzz |
| Paper DOI | https://doi.org/10.1145/3728942 |
| Git repo size (API) | ≈ **183 MiB** (`size` ≈ 186884 KiB) |
| `data/` (measured) | ≈ **1.47 GiB** (`1575191812` bytes; AFL++ / Fuzzotron / GzFuzz / ablations / issue_github) |
| On-disk after clone | ≈ **2.3 GiB** (includes `.git`) |

Layout:

```text
$GZFUZZ_HOME/
  src/                 # GzFuzz Python sources
  data/
    GzFuzz/            # main method runs
    AFL++/             # baseline
    Fuzzotron/         # baseline
    GzFuzz(SC|RC|DC|NL)/  # ablations
    issue_github/      # reported issues
  gazebo_version.txt   # component pins for Gazebo 8.0.0
  Readme.md
```

## Layout (seeds/)

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Mount paths / size notes |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | Python analysis deps |
| `container_setup.sh` | No | Root one-shot Python/torch install |
| `benchmark_config.json` | No | Staging rules |
| `README.md` | No | Human documentation |

## Notes

- Paper target: Gazebo **8.0.0** (Ubuntu 22.04), 12h × 5 runs; i9-13900K / 128GB in paper.
- Sandbox does **not** install full Gazebo; use mounted `data/` for metrics/coverage reanalysis.
- New live fuzzing still needs a host Gazebo Coverage build (see upstream Readme).
