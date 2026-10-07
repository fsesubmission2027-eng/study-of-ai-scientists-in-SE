# Seeds for ISSTA-2025-007 — Top Score on the Wrong Exam (ML4VD validity)

## Agent data policy

Use the mounted TopScoreWrongExam artifact (BigVul / Devign / DiverseVul).
Agent inputs must follow the task protocol; do not inject reduced-budget or
substitute-evaluation guidance.

## Quick start (host)

```bash
cd ~/ai_scientist_inputs/ISSTA-2025-007_assessing_the_validity_of_function_level
chmod +x download_topscorewrongexam_dataset.sh run_aiscientist_benchmark.sh \
  run_airesearcher_benchmark.sh seeds/container_setup.sh
./download_topscorewrongexam_dataset.sh
./run_aiscientist_benchmark.sh run
```

Docker uses `ai-scientist-base:20260615` (`task.env`: `MEMORY=32g`, `CPUS=8`,
`CONTAINER_SETUP=true`). On start, `seeds/container_setup.sh` installs a
scikit-learn / transformers stack into `/opt/issta-2025-007-venv`.

## How to download / sizes

| Item | Value |
|------|-------|
| Host path | `~/ai_scientist_inputs/shared_datasets/topscorewrongexam-issta2025` |
| In-container | `/shared/topscorewrongexam-issta2025` |
| Agent path | `dataset_candidate/topscorewrongexam-issta2025/` |
| Paper artifact | https://github.com/niklasrisse/TopScoreWrongExam |
| Paper DOI | https://doi.org/10.1145/3728887 |
| Devign `function.json` (LFS) | **≈ 61.5 MiB** (61,532,917 bytes) |
| DiverseVul json (LFS) | **≈ 737 MiB** (736,915,162 bytes) |
| RQ1 samples / labels (LFS) | **≈ 58 MiB** |
| BigVul Google Drive zip | **≈ 1.54 GiB** (1,541,009,577 bytes) |
| BigVul `MSR_data_cleaned.csv` uncompressed | **≈ 10.8 GiB** (10,785,616,314 bytes) |
| Total on disk after full extract | **≈ 12–13 GiB** (plus zip if retained) |

Commands:

```bash
# default: clone artifact + git-lfs pull + download/extract BigVul
./download_topscorewrongexam_dataset.sh

# keep BigVul as zip only (~1.54 GiB; no 10.8 GiB CSV)
BIGVUL_MODE=zip_only ./download_topscorewrongexam_dataset.sh
```

Layout after download:

```text
$TOPSCOREWRONGEXAM_HOME/
  original_datasets/
    BigVul/MSR_data_cleaned.csv
    Devign/function.json
    DiverseVul/diversevul_20230702.json
  raw_samples/
  labeled_samples/
  scripts/                 # sampling + scripts/rq_2/*.py
  archives/MSR_data_cleaned.zip
  DOWNLOAD_META.txt
```

## Not included (runtime / optional)

| Component | Notes |
|-----------|--------|
| Devign / ReVeal deep training stacks | Not preinstalled; agent may add PyTorch under `project/` |
| Manual security-expert labeling labor | Paper spent >150 hours; labels for the published sample are in `labeled_samples/` |

## Layout (seeds/)

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Mount paths / size notes |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | sklearn / transformers stack |
| `container_setup.sh` | No | Root one-shot Python install |
| `benchmark_config.json` | No | Staging rules |
| `README.md` | No | Human documentation |
