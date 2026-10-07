# Seeds for ASE-2025-017 — Native Proof Certification for Core-Guided MaxSAT

## Downloaded data

MaxSAT Evaluation 2024 **weighted exact** instances (paper: 571 WCNF formulas):

- source: `https://www.cs.helsinki.fi/group/coreo/MSE2024-instances/mse24-exact-weighted.zip`
- listing: `https://maxsat-evaluations.github.io/2024/benchmarks.html`
- host path: `~/ai_scientist_inputs/shared_datasets/maxsat2024`
- legacy Docker mount: `/shared/maxsat2024` (read-only)
- AI Scientist / aligned path: `dataset_candidate/maxsat2024/`
- environment variable: `MAXSAT2024_HOME=dataset_candidate/maxsat2024`

The zip is ~4.4 GiB. Do **not** re-download it inside the container.

### Dataset files (agent must use these)

| Path | Content |
|------|---------|
| `instances/` | Extracted competition WCNF / `.wcnf.xz` files |
| `instance_index.csv` | Relative path + size for every instance |
| `recommended_subset.txt` | Size-sorted listing of 20 smallest files (not the evaluation protocol) |
| `mse24-exact-weighted.zip` | Official archive (already downloaded) |

Re-download / verify:

```bash
./download_maxsat2024_dataset.sh
```

## C++ / Python environment

`container_setup.sh` automatically creates disposable toolchains at:

```text
/opt/ase-2025-017-venv                         # pandas / numpy / sklearn
/opt/ase-2025-017-tools/EvalMaxSAT             # upstream OLL solver + CaDiCaL
/opt/ase-2025-017-tools/EvalMaxSAT/build/EvalMaxSAT_bin
```

`task.env` puts these first on `PATH`.

```bash
g++ --version
cmake --version
EvalMaxSAT_bin --help
python --version
python -c "import pandas, numpy, sklearn"
```

Upstream EvalMaxSAT **does not** include the paper's native/DAG proof logger.
Implement logging + verification yourself (or wrap the solver). SCIP is **not**
installed.

## Original experimental budget

The paper reports:

- **571** weighted exact instances, 3600 s / 16 GB for solve+log, 7200 s / 16 GB for verify
- EvalMaxSAT solved 435 / 571 in the 2024 competition
- metrics: IR, proof size, verification time, VO, proof-size ratio vs certified-cgss

For AI-Scientist, evaluate the **complete real** 571-instance track. Do not
claim full paper reproduction unless timeouts and resources also match
(3600 s solve / 7200 s verify, 16 GB).

## Running analyses

The mounted package is read-only. Copy before writing:

```bash
mkdir -p project/wcnf
# copy instances into project/, decompress .xz if needed, then solve/log/verify
# evaluate the complete real 571-instance track; write metrics to results/ or artifacts/
```

## Agent-visible files

- `agent/dataset_paths.json`: concrete paths, layout, and copy policy.
- `agent/metrics.json`: required and optional metric keys.
- `benchmark_config.json`, `README.md`, `container_setup.sh`, and `requirements.txt`
  are orchestration/human documentation and are not staged as dataset inputs.
