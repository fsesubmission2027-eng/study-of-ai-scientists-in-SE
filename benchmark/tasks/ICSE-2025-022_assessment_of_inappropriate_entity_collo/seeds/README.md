# Seeds for ICSE-2025-022 — PairSmell (Inappropriate Entity Collocation / Separation)

## Agent data policy

**Agents must not use synthetic pilot CSVs.** Evaluation must run on the **purified
PairSmell dataset** via the shared mount (`PAIRSMELL_HOME=/shared/pairsmell` inside Docker;
agent path `dataset_candidate/pairsmell/`).

**Forbidden leakage:** do not expect or reconstruct paths like `_Agreement/smell_4.csv`
or `insep_smell_4.csv` — those author-computed PairSmell labels were removed from the mount.

Human-only files live in `seeds/` root. Agent-visible config is under `seeds/agent/` only.

## Quick start (host)

```bash
cd ~/ai_scientist_inputs/ICSE-2025-022_assessment_of_inappropriate_entity_collo
chmod +x download_pairsmell_dataset.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh \
  seeds/container_setup.sh
./download_pairsmell_dataset.sh   # skip if shared_datasets/pairsmell already purified
./run_aiscientist_benchmark.sh run
```

Docker uses `ai-scientist-base:20260615` (`task.env`: `MEMORY=32g`, `CPUS=8`,
`CONTAINER_SETUP=true`). On start, `seeds/container_setup.sh` installs analysis deps into
`/opt/icse-2025-022-venv` and mounts the dataset read-only.

## PairSmell dataset (purified)

| Item | Value |
|------|-------|
| Host path | `~/ai_scientist_inputs/shared_datasets/pairsmell` |
| In-container | `/shared/pairsmell` |
| Agent path | `dataset_candidate/pairsmell/` |
| Figshare zip | **≈ 2.53 GiB** (`PairSmell.zip`, 2724097378 bytes, md5 `3cd2ce08b9ededa83cc4d3342df738f4`) |
| Extracted | **≈ 3.5 GiB** (20 projects) |
| DOI | https://doi.org/10.6084/m9.figshare.26268379 |

Layout after purification (flat):

```text
$PAIRSMELL_HOME/
  Arrow/ Kafka/ Hadoop/ ...   # 20 project directories
  COPYING.txt
  DOWNLOAD_META.txt
  README.md
```

Each project snapshot typically retains:

- `entities.txt`, `dependency-file.json`
- `*_modified_commit.json` (co-change / maintenance evidence)
- Modularization tool outputs: `ACDC/`, `FCA/`, `WCA_LIMBO/`, cluster graphs under the project-named folder

Removed from the official package:

- Entire author **Code** / Docker / venv / Supportive tools
- All snapshot `_Agreement/` directories (InSep/InCol CSVs + RQ statistics)

Download original zip (if you need to re-purify from scratch):

```bash
./download_pairsmell_dataset.sh
```

Official package:

- DOI: https://doi.org/10.6084/m9.figshare.26268379
- File: `PairSmell.zip` (~2724097378 bytes / ≈ 2.53 GiB)
- arXiv: https://arxiv.org/abs/2411.01012

## Layout (seeds/)

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | PairSmell mount paths / retained vs removed |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | Extra Python deps for experiments |
| `container_setup.sh` | No | Root one-shot venv install in sandbox |
| `benchmark_config.json` | No | Staging rules for benchmark integration |
| `README.md` | No | Human documentation |

## Notes

- Agent must **detect** InSep/InCol itself from apt MRs (modularization consensus) vs actual
  folder modules — not read deleted `_Agreement` labels.
- Modularization outputs under ACDC/FCA/WCA_LIMBO are part of the dataset inputs, not PairSmell labels.
