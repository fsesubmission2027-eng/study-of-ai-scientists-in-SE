# Seeds for FSE-2025-010 — Pinning vs Floating in npm

## Downloaded data

Official FSE 2025 replication package (Zenodo):

- DOI: `10.5281/zenodo.15121080` (v1.0.1; concept DOI `10.5281/zenodo.14693233`)
- Paper: https://doi.org/10.1145/3715728 (arXiv:2502.06662)
- Host path: `~/ai_scientist_inputs/shared_datasets/pinning-is-futile`
- Legacy Docker mount: `/shared/pinning-is-futile` (read-only)
- AI Scientist / aligned path: `dataset_candidate/pinning-is-futile/`
- Environment variable: `PINNING_IS_FUTILE_HOME=dataset_candidate/pinning-is-futile`

### Size

| Item | Size |
|------|------|
| `pinning-is-futile.zip` (Zenodo) | **548,628,191 bytes (~524 MB)** |
| MD5 | `7c8cc659508a7f87a432fa6e86d33a47` |
| Extracted on disk | **~2.4 GB** |
| Author note | raw `package-lock.json` dumps (~300 GB) are **not** included |

### Key paths inside the artifact

| Path | Content |
|------|---------|
| `data/samples_{npm,woc}_10000.csv` | 10k npm packages + 10k GitHub (WoC) samples (RQ1) |
| `data/sample_dependencies_{npm,woc}.csv` | Version constraints (Figure 1) |
| `data/sample_depgraph_metrics_{npm,woc}_{prod,all}.csv` | Precomputed RQ1 panel metrics |
| `data/depgraph_package_level.csv` | Package-level dependency network (RQ2) |
| `data/npmjs.downloads.*.csv` | Download counts |
| `data/intervention/` | Precomputed intervention risk tables (RQ2) |
| `rq1_*.ipynb` / `rq1_regression.Rmd` / `rq2_*.ipynb` | Author analysis notebooks |
| `scripts/` | Reference data-collection scripts (not turnkey) |

### Download / verify

```bash
./download_pinning_dataset.sh
```

The script downloads from Zenodo, checks size + MD5, and extracts into
`shared_datasets/pinning-is-futile/`. Contents include curated npm/GitHub study
datasets, Jupyter / R Markdown notebooks, and environment config files from the
authors.

## Container toolchain

`container_setup.sh` automatically creates:

```text
/opt/fse-2025-010-venv
```

and installs (when missing):

- Python scientific stack (`pandas`, `statsmodels`, `networkx`, …)
- **Node.js 20 + npm** via NodeSource (DeepScientist needs ≥18; Ubuntu Node 12 is avoided because it leaves `libnode-dev` and breaks Node 20 upgrades)
- R (`Rscript`) for author notebooks when apt provides it

`task.env` puts the venv first on `PATH` and enables `CONTAINER_SETUP=true`.

## Agent-visible files

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Artifact paths and env vars |
| `agent/metrics.json` | Yes | Required metric keys |
| `requirements.txt` | No (pip only) | Python deps for orchestration |
| `container_setup.sh` | No (root setup) | Node/Python/R install |
| `benchmark_config.json` | No | Staging / benchmark rules |
| `README.md` | No | Human documentation |

## Scale note

Full ecosystem-scale historical npm resolution is heavy. Prefer the curated
tables/graphs inside the Zenodo package; document any subsetting. Live registry
scraping is optional and should be rate-limited.
