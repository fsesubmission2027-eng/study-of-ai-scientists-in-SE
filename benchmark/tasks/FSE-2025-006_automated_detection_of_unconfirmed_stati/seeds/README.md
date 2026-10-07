# Seeds for FSE-2025-006 — Automated Detection of Unconfirmed Statistical Assumptions

## Agent data policy

**No pre-bundled notebook corpus.** Agents must **construct** a Kaggle notebook
corpus that calls common hypothesis-testing / regression functions, then evaluate
an annotation-driven assumption checker on those notebooks.

Store under `dataset_candidate/kaggle_notebooks/`.

Human-only files live in `seeds/` root. Agent-visible config is under `seeds/agent/`.

## Dataset download / construction (Kaggle)

Paper corpus: **128** public Kaggle notebooks (Jupyter + R Markdown) using
`scipy.stats` / R `stats` functions, filtered for executability and <10 min runtime.

### Host prerequisite (one-time)

1. Create a Kaggle account API token: https://www.kaggle.com/settings → **API** → **Create New Token**
2. Save as `~/.kaggle/kaggle.json` with mode `600`:

```bash
mkdir -p ~/.kaggle
# place kaggle.json here, then:
chmod 600 ~/.kaggle/kaggle.json
```

`task.env` mounts this directory read-only at `/shared/kaggle` and sets
`KAGGLE_CONFIG_DIR=/shared/kaggle`.

### Inside the container

```bash
# List kernels mentioning a statistical function
kaggle kernels list -s "ttest_ind" --page-size 20

# Download a specific kernel (example)
kaggle kernels pull <owner>/<kernel-slug> -p dataset_candidate/kaggle_notebooks/python/

# Or pull competition/dataset assets referenced by a notebook
kaggle datasets download -d <owner>/<dataset> -p dataset_candidate/kaggle_notebooks/data/
```

### Construction protocol (paper-aligned)

1. Search kernels that textually reference annotated functions
2. Keep only notebooks with a real call site
3. Discard private data sources
4. Discard notebooks that take >10 minutes or fail non-trivially
5. Prefer public, reproducible kernels (data shipped with the notebook)

**Reduced scale OK for a single benchmark run:** 20–40 notebooks covering the
main Python functions is acceptable if documented.

## System toolchain (auto-installed)

`seeds/container_setup.sh` runs as root on container start when
`CONTAINER_SETUP=true` in `task.env`.

Installs:

- Python: `numpy`, `scipy`, `pandas`, `statsmodels`, `jupyter`, `nbconvert`, `kaggle`, …
- R: `r-base` + common packages (`jsonlite`, `rmarkdown`, …)
- Kaggle CLI wiring from `/shared/kaggle/kaggle.json`

Opt out: `CONTAINER_SETUP=false` in `task.env`.

## Layout

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Corpus paths + Kaggle construction steps |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | Orchestration deps |
| `container_setup.sh` | No (root setup) | Toolchain install |
| `benchmark_config.json` | No | Staging / benchmark rules |
| `README.md` | No | Human documentation |

## Method / evaluation sketch

Implement a **prob-check**-style system:

1. Annotate statistical functions with assumptions (normality, equal variance, independence, residual normality)
2. Inject hypothesis tests that emit **warnings only** (do not change return values)
3. Monkey-patch / redefine functions at notebook top, re-run notebooks, count warnings
4. For hypothesis tests with unconfirmed assumptions, compare p-values against non-parametric alternatives (Mann–Whitney, Wilcoxon, Kruskal–Wallis, Welch t-test)

## Metrics

| Metric | RQ |
|--------|----|
| Annotation count | RQ1 |
| Unconfirmed assumption warnings / rates | RQ2 |
| Potential misuse call sites | RQ2/RQ3 |
| Significant misuse rate (different conclusion) | RQ3 |
| Runtime overhead factor (synthetic n=100) | overhead |
