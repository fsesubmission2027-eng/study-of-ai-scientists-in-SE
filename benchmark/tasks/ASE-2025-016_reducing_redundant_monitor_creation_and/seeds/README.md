# Seeds for ASE-2025-016 — Valg Selective Runtime Verification

## Downloaded data

The paper artifact has already been cloned:

- repository: `https://github.com/SoftEngResearch/Valg`
- pinned commit: `7cb06136949976aacac9692b6869dd1d90e2adf0`
- host path: `~/ai_scientist_inputs/shared_datasets/valg`
- legacy Docker mount: `/shared/valg` (read-only)
- AI Scientist / aligned path: `dataset_candidate/valg/`
- environment variable: `VALG_HOME=dataset_candidate/valg`

### Dataset files (agent must use these)

| Path | Content |
|------|---------|
| `data/projects.csv` | 64 open-source Java subjects (single-revision benchmark) |
| `data/shas/` | Per-project revision SHA lists (multi-revision studies) |
| `data/*.csv` | Paper result tables (rq1–rq4, ablation, emop) for reference |
| `experiments/` | JavaMOP / TraceMOP jars + Optuna / evaluation helpers |
| `scripts/` | Docker setup, TraceMOP collect / no-collect runners |
| `javamop/`, `rv-monitor/`, … | Instrumented RV toolchain sources |

Re-download / verify:

```bash
./download_valg_dataset.sh
```

## Java / Python environment

`container_setup.sh` automatically creates disposable toolchains at:

```text
/opt/ase-2025-016-venv          # Python analysis (pandas, optuna, …)
/opt/ase-2025-016-tools         # Maven 3.8.8 + AspectJ 1.9.7
/usr/lib/jvm/java-8-openjdk     # OpenJDK 8 (matches Valg Dockerfile)
```

`task.env` puts these first on `PATH`. The venv and tools dirs are owned by the
unprivileged `agent` user so extra installs work.

```bash
java -version
mvn -version
ajc -version
python --version
python -c "import optuna, pandas, sklearn; from git import Repo"
```

## Original experimental budget

The paper evaluates:

- **64** single-revision Java projects (`data/projects.csv`)
- **46** multi-revision projects (SHA lists under `data/shas/`)
- baselines: JavaMOP and TraceMOP jars under `experiments/`
- CPU-only (no GPU); full TraceMOP + 64 subjects is many CPU-hours

For AI-Scientist, use a **reduced and explicitly reported** protocol (e.g. 3–10
projects, JavaMOP-only first). Do not claim full paper reproduction unless the
protocol and resources match.

## Running analyses

The mounted package is read-only. Copy before writing:

```bash
cp -a "$VALG_HOME/scripts" project/valg_scripts
cp -a "$VALG_HOME/experiments" project/valg_experiments
# clone subjects at SHAs from data/projects.csv into project/, then run
# write metrics to results/ or artifacts/
```

For read-only custom analysis, scripts may read `$VALG_HOME` directly and write
results under `project/` or `artifacts/`.

## Agent-visible files

- `agent/dataset_paths.json`: concrete paths, layout, commit, and copy policy.
- `agent/metrics.json`: required and optional metric keys.
- `benchmark_config.json`, `README.md`, `container_setup.sh`, and `requirements.txt`
  are orchestration/human documentation and are not staged as dataset inputs.
