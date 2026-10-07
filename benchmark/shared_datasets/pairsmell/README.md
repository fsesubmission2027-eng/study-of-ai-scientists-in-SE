# PairSmell shared dataset (purified for AI Scientist benchmark)

**Agent access path (use this in `ls` / `read_file` and in scripts with cwd = run root):**

```text
dataset_candidate/pairsmell/
```

Set `PAIRSMELL_HOME=dataset_candidate/pairsmell` (or `os.environ["PAIRSMELL_HOME"]`).

Do **not** use absolute host paths or `/shared/*` with file tools.

## Layout

**~20 project directories** at the dataset root, each containing **snapshot subdirectories** (not a flat file list at the root).

Example entity file path:

```text
dataset_candidate/pairsmell/<project>/<snapshot>/entities.txt
```

Also at the dataset root (data + provenance only):

- `COPYING.txt` — license
- `DOWNLOAD_META.txt` — Figshare DOI / checksum metadata (no methodology)

## What is retained (inputs)

Per snapshot under each project:

- `entities.txt`, `dependency-file.json`
- `*_modified_commit.json` (and rename records where present)
- Modularization tool outputs: `ACDC/`, `FCA/`, `WCA_LIMBO/`, cluster graphs

## What was removed (leakage / non-dataset)

- `PACKAGE_README.md` — author replication guide (ICSE 2025 methodology & expected outputs)
- Author Code, Docker images (`pairsmell` / `pairsmell.tar`), venv, Supportive tools, `.git`
- All `_Agreement/` directories: `smell_4.csv`, `insep_smell_4.csv`, statistics CSVs
- Outer `PairSmell.zip` / `__MACOSX`

Source DOI: https://doi.org/10.6084/m9.figshare.26268379
