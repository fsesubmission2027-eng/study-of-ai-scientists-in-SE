# Seeds for ISSTA-2025-004 — Hulk (data-sensitive DBMS performance anomalies)

## Agent data policy

There is **no fixed downloadable SQL/data corpus**. The paper constructs schemas,
incremental data, and data-sensitive queries **on-the-fly**.

**Hulk itself is not publicly packaged** (no GitHub/Zenodo artifact found).
Mount open baselines under
`HULK_ISSTA2025_BASELINES_HOME=/shared/hulk-issta2025-baselines`
(agent path `dataset_candidate/hulk-issta2025-baselines/`).

Agent inputs must follow the task protocol; do not inject reduced-budget or substitute-evaluation guidance.

## Quick start (host)

```bash
cd ~/ai_scientist_inputs/ISSTA-2025-004_automatically_detecting_data_sensitive_p
chmod +x download_hulk_baselines.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh \
  seeds/container_setup.sh
./download_hulk_baselines.sh
./run_aiscientist_benchmark.sh run
```

Docker uses `ai-scientist-base:20260615` (`task.env`: `MEMORY=32g`, `CPUS=8`,
`CONTAINER_SETUP=true`). On start, `seeds/container_setup.sh` installs Java 17 +
Python DB clients into `/opt/issta-2025-004-venv`.

## What you can download

| Item | Value |
|------|-------|
| Host path | `~/ai_scientist_inputs/shared_datasets/hulk-issta2025-baselines` |
| In-container | `/shared/hulk-issta2025-baselines` |
| Agent path | `dataset_candidate/hulk-issta2025-baselines/` |
| Paper DOI | https://doi.org/10.1145/3728973 |
| Paper PDF | http://wingtecher.com/themes/WingTecherResearch/assets/papers/paper_from_25/HULK_ISSTA25.pdf |
| Workload dataset | **constructable** — no download size |
| Hulk tool | **not publicly released** |
| Open baselines (measured) | **≈ 290 MiB** total |
| — APOLLO | ≈ **272 MiB** |
| — SQLancer | ≈ **13 MiB** |
| — Squirrel | ≈ **5.9 MiB** |

Layout after download:

```text
$HULK_ISSTA2025_BASELINES_HOME/
  apollo/      # https://github.com/sslab-gatech/apollo
  sqlancer/    # https://github.com/sqlancer/sqlancer
  squirrel/    # https://github.com/s3team/Squirrel
  DOWNLOAD_META.txt
```

## Not included (large / runtime)

| Component | Notes |
|-----------|--------|
| Synthetic workload | Generated during testing |
| MySQL / MariaDB / Percona / TiDB / PostgreSQL / AntDB | Official Docker images or sources; multi-GB if built |
| Full paper campaign | Up to **2 weeks × 6 DBMSs**, 5 CPU / 32 GiB per container |

## Layout (seeds/)

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Mount paths / status notes |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | Python analysis / DB clients |
| `container_setup.sh` | No | Root one-shot Java/Python install |
| `benchmark_config.json` | No | Staging rules |
| `README.md` | No | Human documentation |
