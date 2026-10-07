# Seeds for ISSTA-2025-009 — LLM4SZZ (bug-inducing commit identification)

## Agent data policy

Use the mounted LLM4SZZ Figshare artifact (DS_LINUX / DS_GITHUB / DS_APACHE,
source, and saved LLM logs). Agent inputs must follow the task protocol; do not
inject reduced-budget or substitute-evaluation guidance.

## Quick start (host)

```bash
cd ~/ai_scientist_inputs/ISSTA-2025-009_improving_bug_inducing_commit_identifica
chmod +x download_llm4szz_dataset.sh run_aiscientist_benchmark.sh \
  run_airesearcher_benchmark.sh seeds/container_setup.sh
./download_llm4szz_dataset.sh
./run_aiscientist_benchmark.sh run
```

Docker uses `ai-scientist-base:20260615` (`task.env`: `MEMORY=32g`, `CPUS=8`,
`CONTAINER_SETUP=true`). On start, `seeds/container_setup.sh` installs a
GitPython / tree-sitter / OpenAI client stack into `/opt/issta-2025-009-venv`.

## How to download / sizes

| Item | Value |
|------|-------|
| Host path | `~/ai_scientist_inputs/shared_datasets/llm4szz-issta2025` |
| In-container | `/shared/llm4szz-issta2025` |
| Agent path | `dataset_candidate/llm4szz-issta2025/` |
| Figshare | https://figshare.com/articles/conference_contribution/LLM4SZZ_-_Source_code_and_Dataset/27418236 |
| Figshare DOI | https://doi.org/10.6084/m9.figshare.27418236.v1 |
| Paper DOI | https://doi.org/10.1145/3728885 |
| Figshare zip | **≈ 124.1 MiB** (130,088,880 bytes) |
| Extracted package | **≈ 980 MiB** apparent (`dataset/` ~2.6 MiB; `save_logs/` ~931 MiB, 24,106 files) |
| `DS_LINUX.json` | **1,500** cases (~646 KiB) |
| `DS_GITHUB.json` | **361** cases (~89 KiB) |
| `DS_APACHE.json` | **243** cases (~40 KiB) |
| `final_all_dataset.json` | **2,127** cases (~448 KiB) |

Commands:

```bash
# default: download Figshare zip + extract
./download_llm4szz_dataset.sh
```

Layout after download:

```text
$LLM4SZZ_HOME/   # package/ -> replication/llmszz-replication-package1
  dataset/
    DS_LINUX.json
    DS_GITHUB.json
    DS_APACHE.json
    final_all_dataset.json
    DS_*_EXTEND.json
  llm4szz.py                 # RQ1 pipeline
  llm4szz_{c,h,r,raw,re}.py  # RQ2 variants
  cal_statistics.py
  save_logs/                 # paper LLM outputs
  build/my-languages.so      # tree-sitter
  environment.yml
  readme.md
```

## Not included (runtime / optional)

| Component | Notes |
|-----------|--------|
| Subject git clones (Linux / Apache / GitHub repos) | Required at runtime for blame/context; configure paths in `constants.py` |
| Llama-3-8B / 70B weights | Not preinstalled; paper RQ3 optional local models |
| NeuralSZZ / Rosa SZZ Unleashed full packages | Not bundled in this Figshare zip; agent may fetch separately for baselines |
| Full CUDA / torch stack | Omitted from container seed; add under `project/` if needed |

## Layout (seeds/)

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Mount paths / size notes |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | GitPython / tree-sitter / OpenAI stack |
| `container_setup.sh` | No | Root one-shot Python install |
| `benchmark_config.json` | No | Staging rules |
| `README.md` | No | Human documentation |
