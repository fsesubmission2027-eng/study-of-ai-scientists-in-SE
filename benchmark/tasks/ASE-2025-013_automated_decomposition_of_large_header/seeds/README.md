# Seeds for ASE-2025-013 — HFDecomposer Header File Decomposition

## Downloaded data

The paper artifact has already been cloned:

- repository: `https://github.com/HFDecomposer/HFDecomposer`
- pinned commit: `1ae24c566118162e68a9dd816d270f7ced032016`
- host path: `~/ai_scientist_inputs/shared_datasets/hfdecomposer`
- legacy Docker mount: `/shared/hfdecomposer` (read-only)
- AI Scientist / aligned path: `dataset_candidate/hfdecomposer/`
- environment variable: `HFDECOMPOSER_HOME=dataset_candidate/hfdecomposer`

### Dataset files (agent must use these)

| Path | Content |
|------|---------|
| `dataset/filtered_data.csv` | 153 ground-truth decomposition summaries |
| `dataset/header_files/` | 153 instances; each has original header + `refactoring_ground_truth/` |
| `dataset/openssl_7436/` | Example project used by `source_code/example.ipynb` |
| `source_code/` | Author HFDecomposer implementation (reference / optional reuse) |

Re-download / verify:

```bash
./download_hfdecomposer_dataset.sh
```

## Python / C environment

`container_setup.sh` automatically creates a disposable environment at:

```text
/opt/ase-2025-013-venv
```

It installs networkx, tree-sitter-c, scikit-learn, pandas, GitPython, openai, and related
packages, plus `clang` / `gcc` for optional compile checks. `task.env` puts this
environment first on `PATH`. The venv is owned by the unprivileged `agent` user so
extra `pip install`s work.

```bash
python --version
python -c "import networkx, pandas, sklearn, tree_sitter_c; from git import Repo"
```

## Original experimental budget

The paper does **not** report wall-clock hours. It reports:

- evaluation set: **153** real-world header decompositions from top-100 starred C projects
- models: GPT-4o and DeepSeek-V3 via commercial APIs (temperature 0)
- long files: headers with ≥200 entities use the two-stage grouping framework
- local work: Tree-sitter parsing, similarity graphs, hallucination / cycle fixes (CPU-light)
- cost note: API tokens and LLM response latency dominate practical cost

For AI-Scientist, use a **reduced and explicitly reported** protocol (subset of headers,
local/cheaper LLM, or non-LLM clustering ablations). Do not claim full paper
reproduction unless the protocol and resources match.

## Running analyses

The mounted package is read-only. Copy before writing:

```bash
cp -a "$HFDECOMPOSER_HOME/source_code" project/hfdecomposer_src
cp -a "$HFDECOMPOSER_HOME/dataset" project/hfdecomposer_data
# adapt / evaluate under project/; write metrics to results/ or artifacts/
```

For read-only custom analysis, scripts may read `$HFDECOMPOSER_HOME` directly and
write results under `project/` or `artifacts/`.

## Agent-visible files

- `agent/dataset_paths.json`: concrete paths, layout, commit, and copy policy.
- `agent/metrics.json`: required and optional metric keys.
- `benchmark_config.json`, `README.md`, `container_setup.sh`, and `requirements.txt`
  are orchestration/human documentation and are not staged as dataset inputs.
