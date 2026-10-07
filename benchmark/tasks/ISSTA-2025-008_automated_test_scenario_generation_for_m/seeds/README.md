# Seeds for ISSTA-2025-008 — COLREGS ASV scene generation (CommonOcean)

## Agent data policy

Use the mounted ASVTestSceneGeneration artifact (CommonOcean XML scenarios,
COLREGS functional equivalence-class models, and SB/RS code). Agent inputs must
follow the task protocol; do not inject reduced-budget or substitute-evaluation
guidance.

## Quick start (host)

```bash
cd ~/ai_scientist_inputs/ISSTA-2025-008_automated_test_scenario_generation_for_m
chmod +x download_asvtestscenegeneration_dataset.sh run_aiscientist_benchmark.sh \
  run_airesearcher_benchmark.sh seeds/container_setup.sh
./download_asvtestscenegeneration_dataset.sh
./run_aiscientist_benchmark.sh run
```

Docker uses `ai-scientist-base:20260615` (`task.env`: `MEMORY=32g`, `CPUS=8`,
`CONTAINER_SETUP=true`). On start, `seeds/container_setup.sh` installs a
pymoo / Scenic / Shapely stack into `/opt/issta-2025-008-venv`.

## How to download / sizes

| Item | Value |
|------|-------|
| Host path | `~/ai_scientist_inputs/shared_datasets/asvtestscenegeneration-issta2025` |
| In-container | `/shared/asvtestscenegeneration-issta2025` |
| Agent path | `dataset_candidate/asvtestscenegeneration-issta2025/` |
| Paper artifact | https://github.com/PELAB-LiU/ASVTestSceneGeneration |
| Paper DOI | https://doi.org/10.1145/3728919 |
| CommonOcean upstream | https://commonocean.cps.cit.tum.de/ |
| CommonOcean XML total | **3,934 files**, **≈ 271 MiB** under `assets/common_ocean_scenarios/` |
| Florida | 545 XML, ≈ 30 MiB |
| MiddleEastCoast | 667 XML, ≈ 39 MiB |
| UpperWestCoast | 722 XML, ≈ 50 MiB |
| HandcraftedTwoVesselEncounters_01_24 | 2,000 XML, ≈ 165 MiB |
| Functional models | `<1 MiB` under `assets/functional_models/` |
| Evaluation `gen_data/` | **≈ 67 MiB** |
| Total working tree on disk | **≈ 389–460 MiB** (including `.git`) |

Commands:

```bash
# default: shallow-clone paper artifact (includes CommonOcean XMLs)
./download_asvtestscenegeneration_dataset.sh
```

Layout after download:

```text
$ASVTESTSCENEGENERATION_HOME/
  assets/
    common_ocean_scenarios/
      Florida/
      MiddleEastCoast/
      UpperWestCoast/
      HandcraftedTwoVesselEncounters_01_24/
    functional_models/{all,ambiguous}/   # K=2..6 equivalence classes
    scenic/                              # Scenic RS scenario specs
    gen_data/                            # paper evaluation batches
  src/
    scripts/evaluation_main.py           # SB (pymoo NSGA-II) evaluation
    scripts/scenic_script.py             # RS (Scenic) evaluation
    scripts/common_ocean_scenario_parser.py
    commonocean/                         # vendored CommonOcean-IO parser
  refinery_functional_models/
  requirements.txt
  DOWNLOAD_META.txt
```

## Not included (runtime / optional)

| Component | Notes |
|-----------|--------|
| MOOS-IvP / ArduPilot SITL | Not preinstalled; high-fidelity simulators are out of paper scope for initial-scene generation |
| Windows-only deps (`pywin32`, `tkfilebrowser`) | Omitted from Linux container requirements |
| Separate CommonOcean GitLab clone | Not required; paper artifact already vendors the CO scenarios used in the evaluation |

## Layout (seeds/)

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Mount paths / size notes |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | pymoo / Scenic / Shapely stack |
| `container_setup.sh` | No | Root one-shot Python install |
| `benchmark_config.json` | No | Staging rules |
| `README.md` | No | Human documentation |
