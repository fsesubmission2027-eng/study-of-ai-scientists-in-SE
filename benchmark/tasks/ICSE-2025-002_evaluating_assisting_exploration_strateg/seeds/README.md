# Seeds for ICSE-2025-002 — Assisting Exploration Strategies / CDFUZZ

## Downloaded data

The paper artifact is cloned on the host:

| Item | Value |
|------|-------|
| Primary repo | `https://github.com/SophrosyneX/Fuzzing-empirical-study.git` |
| Paper citation repo | `https://github.com/GhabiX/CDFuzz.git` (same CDFuzz tree) |
| Host path | `~/ai_scientist_inputs/shared_datasets/fuzzing-empirical-study` |
| Docker mount | `/shared/fuzzing-empirical-study` (read-only) |
| Agent path | `dataset_candidate/fuzzing-empirical-study/` |
| Env var | `FUZZING_EMPIRICAL_STUDY_HOME=dataset_candidate/fuzzing-empirical-study` |

Re-download / verify:

```bash
./download_fuzzing_empirical_study.sh
```

### What is in the git clone (~15 MB)

| Path | Content |
|------|---------|
| `CDFuzz/` | CDFUZZ fuzzer source (AFL fork + llvm_mode dictionary analysis) |
| `Experiment/seed/` | **16** initial seed corpora (one dir per program) |
| `Experiment/build-bench.sh` | Script to clone/build **14** real-world fuzz targets |
| `Demo/jhead` + `Demo/fuzzing/` | Minimal end-to-end jhead fuzzing example |
| `README.md` | Build instructions, benchmark selection table, bug reports |

### What is NOT in the clone (must build separately)

- **21 paper benchmark binaries** — sources fetched by `build-bench.sh` or upstream repos (binutils-gdb, libxml2, libjpeg, libtiff, mupdf, tcpdump, …)
- **Other paper fuzzers** — QSYM, MEUZZ, Pangolin, Angora, REDQUEEN, MOpt, FairFuzz (separate GitHub repos)
- **FuzzingDriver auto-dictionaries** — not bundled

After running `Experiment/build-bench.sh`, expect **several GB** of downloaded sources and build artifacts (binutils-gdb alone is large).

## Docker / container environment

`task.env` + `container_setup.sh` prepare:

- Ubuntu 22.04 base image `ai-scientist-base:20260615`
- **LLVM-13** + **clang-13** (`/usr/lib/llvm-13/bin` on PATH)
- **AFL++** (`afl-fuzz`, `afl-clang-fast`) for baselines
- build-essential, cmake, autoconf, libpcap-dev, …
- Python venv: `/opt/icse-2025-002-venv`

On container start, `container_setup.sh` also attempts to compile CDFuzz from the mounted artifact.

## Launch benchmark

```bash
./download_fuzzing_empirical_study.sh          # once on host
./run_airesearcher_benchmark.sh run            # or run_aiscientist_benchmark.sh
```

## Evaluation protocol (default)

Full ICSE 2025 paper protocol: **21 programs × 9 studied fuzzers + CDFUZZ × 24 hours × 5 repeats**, LLVM-13 instrumentation, automatic dictionaries (FuzzingDriver-style). Agent is expected to build all targets and fuzzers and run the complete grid (parallelize across CPUs).
