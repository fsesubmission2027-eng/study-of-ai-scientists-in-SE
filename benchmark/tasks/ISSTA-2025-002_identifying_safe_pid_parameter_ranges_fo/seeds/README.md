# Seeds for ISSTA-2025-002 — RouthSearch (UAV PID safe-range identification)

## Agent data policy

Use the **RouthSearch tool artifact** via the shared mount
(`ROUTHSEARCH_HOME=/shared/routhsearch-issta2025` inside Docker;
agent path `dataset_candidate/routhsearch-issta2025/`).

Mounted inputs include `routh_search/` oracles and sample `oracle_logs/`.
Agent inputs must follow the task protocol; do not inject reduced-budget or
substitute-evaluation guidance.

Human-only files live in `seeds/` root. Agent-visible config is under `seeds/agent/` only.

## Quick start (host)

```bash
cd ~/ai_scientist_inputs/ISSTA-2025-002_identifying_safe_pid_parameter_ranges_fo
chmod +x download_routhsearch.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh \
  seeds/container_setup.sh
./download_routhsearch.sh
./run_aiscientist_benchmark.sh run
```

Docker uses `ai-scientist-base:20260615` (`task.env`: `MEMORY=32g`, `CPUS=8`,
`CONTAINER_SETUP=true`). On start, `seeds/container_setup.sh` installs pymavlink +
analysis deps into `/opt/issta-2025-002-venv`.

## Dataset (RouthSearch GitHub AE)

| Item | Value |
|------|-------|
| Host path | `~/ai_scientist_inputs/shared_datasets/routhsearch-issta2025` |
| In-container | `/shared/routhsearch-issta2025` |
| Agent path | `dataset_candidate/routhsearch-issta2025/` |
| GitHub | https://github.com/SciC0d3m4xOfW/RouthSearch |
| Paper DOI | https://doi.org/10.1145/3728904 |
| Git repo size (API) | ≈ **24.2 MiB** (`size` ≈ 24790 KiB) |
| Blob payload (sum) | ≈ **53.4 MiB** (mostly sample `oracle_logs` `.BIN`/`.ulg`) |
| On-disk after clone (measured) | ≈ **79 MiB** (includes `.git`) |
| Ground-truth benchmark | **Not packaged** — constructable via SITL/jMAVSim (~**7000 CPU hours**) |

Layout:

```text
$ROUTHSEARCH_HOME/
  routh_search/
    ardupilot/          # flight tasks + offline oracles (+ sample oracle_logs/)
    px4/                # PX4 modes + oracles (+ sample oracle_logs/)
  evaluation_script/    # boundary-search shell scripts per flight mode
  ardupilot_default_data/
  README.md
```

## Layout (seeds/)

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Mount paths / size notes |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | Python analysis deps |
| `container_setup.sh` | No | Root one-shot Python/pymavlink install |
| `benchmark_config.json` | No | Staging rules |
| `README.md` | No | Human documentation |

## Notes

- Paper subjects: ArduPilot Copter V4.4.1 (SITL), PX4 V1.15.0 (jMAVSim); 8 flight modes.
- Sandbox does **not** install full ArduPilot/PX4 simulators; use mounted code/logs for metrics/oracle reanalysis.
- New live boundary search still needs host SITL/jMAVSim (see upstream README).
- Baseline PGFuzz is separate and was not packaged with this AE.
