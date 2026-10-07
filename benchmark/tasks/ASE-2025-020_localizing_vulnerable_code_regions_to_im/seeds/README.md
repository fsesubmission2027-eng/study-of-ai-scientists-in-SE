# Seeds for ASE-2025-020 — Localizing Vulnerable Code Regions (LOSVER)

## Downloaded data

LOSVER replication code plus the three paper datasets:

- code: `https://github.com/waroad/losver` (pinned `a158905cb45b4400f481f18eeb1cb4473ccfccdc`)
- host path: `~/ai_scientist_inputs/shared_datasets/losver`
- legacy Docker mount: `/shared/losver` (read-only)
- AI Scientist / aligned path: `dataset_candidate/losver/`
- environment variables:
  - `LOSVER_HOME=dataset_candidate/losver`
  - `DEVIGN_HOME=dataset_candidate/losver/datasets/devign`
  - `BIGVUL_HOME=dataset_candidate/losver/datasets/bigvul`
  - `PRIMEVUL_HOME=dataset_candidate/losver/datasets/primevul`
  - `LOSVER_REPOS=dataset_candidate/losver/repos`

### Dataset files (agent must use these)

| Path | Content |
|------|---------|
| `source_code/` | Author LOSVER scripts (`detection/`, `classification/`, `detection_primevul/`) |
| `datasets/devign/train.jsonl` | CodeXGLUE Defect-detection train split (21,854 functions) |
| `datasets/devign/valid.jsonl` | Dev / validation split (2,732) |
| `datasets/devign/test.jsonl` | Test split (2,732) |
| `datasets/bigvul/MSR_data_cleaned.json` | Vulnerable-only JSON dict (10,895 records) for the author `bigvul_preprocess.py` |
| `datasets/bigvul/MSR_data_cleaned.jsonl` | Full Big-Vul JSONL (217,007 functions, 10,895 vulnerable) |
| `datasets/primevul/primevul_train_paired.jsonl` | PrimeVul paired train split (7,578 functions) |
| `datasets/primevul/primevul_valid_paired.jsonl` | PrimeVul paired validation split (960) |
| `datasets/primevul/primevul_test_paired.jsonl` | PrimeVul paired test split (870) |
| `datasets/devign/{train,valid,test}_with_lines.jsonl` | Same records plus `lines_ground_truth` (0-based modified-line indices, `[-1]` when unrecoverable) and `line_gt_status` |
| `datasets/devign/line_gt_summary.json` | Per-split line-GT recovery coverage and failure breakdown |
| `repos/FFmpeg`, `repos/qemu` | Bare clones of the two Devign upstream projects, so `devign_preprocess.py` can `git show` any historical commit offline |

Re-download / verify:

```bash
./download_losver_dataset.sh          # datasets + source code + FFmpeg/qemu clones
./build_devign_line_gt.py             # regenerate *_with_lines.jsonl from the clones
```

### Devign line-level ground truth

Devign's released jsonl stores only the vulnerable function (`commit_id, func, idx,
project, target`) — there is no `func_after`, so the modified-line labels required by
`top_n_accuracy` and `line_level_f1` cannot be derived from the jsonl alone. Following
the authors' `devign_preprocess.py`, the patched function is recovered from the FFmpeg
and qemu histories and diffed against the vulnerable one. Both repositories are bare
clones under `$LOSVER_REPOS` and every Devign commit resolves in them, so this runs
fully offline. Big-Vul (`func_before`/`func_after`) and PrimeVul (paired records)
already carry the information needed for line-level GT.

## Intentionally not downloaded

| Artifact | Why skipped |
|----------|-------------|
| Figshare checkpoints (`10.6084/m9.figshare.29192708`) | Author-trained weights, not the evaluation tables. Optional if you later want to score the authors' models without training. |
| UniXcoder / CodeBERT / CodeT5+ weights | Download at runtime with `source_code/download_unixcoder.py` or `transformers`. Do not bake multi-hundred-MB checkpoints into the shared mount. |

## Python environment

Do not create or activate a virtual environment inside the shared repository.
`container_setup.sh` automatically creates a disposable environment at:

```text
/opt/ase-2025-020-venv
```

It installs CPU PyTorch + transformers so startup works without NVIDIA drivers.
`task.env` puts this environment first on `PATH`. The venv is owned by the
unprivileged `agent` user so extra `pip install`s work.

```bash
python --version
python -c "import torch, transformers, pandas, sklearn"
```

## Original experimental budget

The paper reports:

- hardware: Tesla V100-PCIE-32GB (shared academic cluster)
- UniXcoder 512-token detection, end-to-end (localizer + detector): **12 hours / 1 GPU**
- localizer: 40 epochs; detector: 8 epochs (detection) / 16 epochs (classification)
- lr `2e-5`, batch size 8, AdamW, seed `123456`
- Devign filtered to 19,771 (UniXcoder 512); Big-Vul filtered to 6,924 / 36 CWE IDs; PrimeVul paired, unfiltered

For AI-Scientist, use a **reduced and explicitly reported** protocol (subset of
functions, fewer epochs, CPU or a single small PLM). Do not claim full paper
reproduction unless the protocol and resources match.

## Running analyses

The mounted package is read-only. Copy before writing:

```bash
cp -a "$LOSVER_HOME/source_code" project/losver
mkdir -p project/data
cp -a "$DEVIGN_HOME" project/data/devign
cp -a "$BIGVUL_HOME" project/data/bigvul
cp -a "$PRIMEVUL_HOME" project/data/primevul
# preprocess / train under project/; write metrics to results/ or artifacts/
# The bare clones under $LOSVER_REPOS stay read-only; git show reads them in place.
```

For read-only custom analysis, scripts may read `$LOSVER_HOME` directly and
write results under `project/` or `artifacts/`.

## Agent-visible files

- `agent/dataset_paths.json`: concrete paths, layout, commit, and copy policy.
- `agent/metrics.json`: required and optional metric keys.
- `benchmark_config.json`, `README.md`, `container_setup.sh`, and `requirements.txt`
  are orchestration/human documentation and are not staged as dataset inputs.
