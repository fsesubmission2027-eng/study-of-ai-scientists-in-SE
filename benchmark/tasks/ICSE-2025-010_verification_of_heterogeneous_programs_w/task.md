# Task: ICSE-2025-010 — Verification of Heterogeneous Programs with Inaccessible Source Code

## Background

Modern software frequently integrates components written in multiple programming languages, and critical third-party libraries whose source code is not available. This heterogeneity makes program verification challenging, as many existing tools require full source code. Approaches like decompilation or direct abstraction often fail to guarantee semantic equivalence or are restricted to specific architectures and standards. Therefore, a robust verification approach is needed for programs that contain unverifiable segments—such as low-level code or missing functions—without requiring source code access or sacrificing correctness.

## Research Question

How can programs that include components with missing source code or low-level code be accurately verified, ensuring semantic equivalence with the original program without requiring the inaccessible source?

## Experiment Setup

### Datasets
```
- name: RISC-V Assembly Programs from SV-COMP
  source: SV-COMP 2024 (https://sv-comp.sosy-lab.org/2024/)
  description: 100 C programs selected from SV-COMP 2024 (50 correct, 50 incorrect), each with 1–3 functions, modified to remove non-essential functions and compiled to RISC-V assembly using riscv64-unknown-elf-gcc.
  access: constructable
- name: Large Heterogeneous C Programs with Missing Functions
  source: SV-COMP 2024 and SV-COMP 2023 (https://sv-comp.sosy-lab.org/2023/)
  description: 30 verification tasks (15 correct, 15 incorrect) with >5 functions and >300 lines (average >1000 lines). Functions highly correlated with verification were removed and compiled into RISC-V static libraries.
  access: constructable
- name: RISC-V Binary Programs
  source: Derived from RISC-V Assembly Programs dataset
  description: 100 assembly programs compiled into RISC-V binary executables for decompiler comparison.
  access: constructable
```

### Baselines
```
- name: Direct CBMC verification
  reference: CBMC (https://www.cprover.org/cbmc/) on the source code with missing functions replaced by stubs
- name: IDA Pro
  reference: Hex-Rays IDA Pro (https://hex-rays.com/ida-pro/)
- name: Ghidra
  reference: NSA Ghidra (https://ghidra-sre.org/)
```

### Metrics
```
- name: Correctness Rate
  definition: Correct Verifications divided by Total Tests
- name: Error Rate
  definition: 1 minus (Correct Verifications + Timeouts) divided by Total Tests
```

### Sub-questions
```
- RQ1: Can the approach effectively verify low-level language (assembly) programs?
- RQ2: Is the approach capable of verifying large-scale heterogeneous programs with missing source code functions?
- RQ3: Can existing decompiler tools such as IDA Pro and Ghidra serve as viable alternatives to the proposed approach?
```

### Target Subject

Program verification tasks involving RISC-V assembly, large C programs with some functions replaced by compiled libraries (missing source code), and RISC-V binary executables. Example tasks are drawn from the SV-COMP benchmark suites.

### Constraints

All programs must be compilable to RISC-V binaries. CBMC must be used as the backend verifier with a timeout of 3000 seconds per program. For correct programs, loop unwind factor is fixed to 20; for incorrect programs, no fixed unwind factor is applied. Environment: Ubuntu 22.04 LTS, RISC-V GCC toolchain (riscv64-unknown-elf-gcc).

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The SV-COMP benchmarks are publicly accessible, and compilation to RISC-V is well-supported by GCC. The experiments involve a large number of verification runs with a 3000-second timeout, which may require significant compute time (potential total >80 CPU-hours). A high-memory machine (the original used 384 GB RAM) may be needed for some large programs, though typical benchmarks are less demanding. Building the tool and environment requires knowledge of CBMC and RISC-V toolchains.

### Harness (AI Scientist / container)

This task is wired like ICSE-2025-005/008:

| File | Role |
|------|------|
| `download_hetrify_svcomp.sh` | Host-side download of SV-COMP (+ CBMC deb, optional Ghidra) |
| `task.env` | Docker image, `MEMORY=64g`, `CPUS=8`, mount `shared_datasets/hetrify-svcomp` |
| `seeds/container_setup.sh` | Install CBMC from mounted `.deb`, `gcc-riscv64-unknown-elf`, OpenJDK 17, Python venv |
| `run_aiscientist_benchmark.sh` / `run_airesearcher_benchmark.sh` | Launchers |

```bash
chmod +x download_hetrify_svcomp.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh
./download_hetrify_svcomp.sh                    # default: SV-COMP 2024 + CBMC (~1.8 GiB)
# FETCH_MODE=both ./download_hetrify_svcomp.sh  # + SV-COMP 2023 (~+1.4 GiB)
# FETCH_MODE=all ./download_hetrify_svcomp.sh   # + Ghidra (~+569 MiB)
./run_aiscientist_benchmark.sh run
```

**Shared data root:** `~/ai_scientist_inputs/shared_datasets/hetrify-svcomp`  
**In-container mount:** `/shared/hetrify-svcomp` → agent `dataset_candidate/hetrify-svcomp/`

### Dataset sizes (verified)

| Resource | Size |
|----------|------|
| SV-COMP 2024 zip (Zenodo 10669723) | **~1.76 GiB** (1,756,960,125 B) |
| SV-COMP 2023 zip (Zenodo 7627783) | **~1.40 GiB** (1,396,566,648 B) |
| CBMC 5.95.1 Ubuntu 22.04 `.deb` | **~67 MB** |
| Ghidra PUBLIC zip (optional) | **~569 MiB** |
| RISC-V GCC | apt in container (not in shared zip) |
| IDA Pro | commercial — not provided |
| Hetrify tool | https://anonymous.4open.science/r/Hetrify (may expire) |

Paper evaluation sets (100 + 30 + 100 binaries) are **constructed** from SV-COMP, not a separate download. Sandbox RAM (64g) is far below the paper’s 384 GB — use a disclosed reduced subset/timeout when needed.

## Metadata

```
subfield: Program Analysis & Verification
venue: ICSE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```