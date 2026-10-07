# Task: ISSTA-2025-006 — Precise and Efficient Points-to Analysis for Stripped Binary Executables

## Background

Pointer analysis is a cornerstone of binary reverse engineering, enabling critical tasks such as call graph reconstruction, value flow analysis, and security vulnerability detection. In stripped binaries, source-level types and symbols are absent, forcing analysis to treat every register and memory location as a potential pointer and to account for pointer arithmetic and type casts. Existing approaches range from arity-based and machine-learning-based to program-analysis-based techniques (e.g., VSA, BPA, BinPointer), but none simultaneously deliver high precision, high efficiency, and acceptable soundness. Current methods are either too imprecise, producing many false positives, or too slow to scale to large programs. This gap calls for a binary pointer analysis that prioritises precision and efficiency while remaining soundy—sacrificing soundness only in controlled, limited circumstances.

## Research Question

How can we design a binary pointer analysis that achieves high precision and high efficiency while sacrificing soundness only in limited, well-defined situations?

## Experiment Setup

### Datasets
```
- name: SPEC CPU2006 C benchmarks
  source: https://www.spec.org/cpu2006/
  description: C benchmarks from SPEC CPU2006 that contain indirect calls, including programs like 403.gcc, 464.h264ref, and 482.sphinx3. Compiled with GCC-9.2 at -O2, stripped.
  access: restricted
- name: Open-source server applications
  source: official project websites for thttpd-2.29, memcached-1.5.4, lighttpd-1.4.48, exim-4.89, nginx-1.10
  description: Five real-world, security-critical C applications compiled with GCC-9.2 at -O2 and stripped. Used to evaluate indirect call recovery and scalability.
  access: open
```

### Baselines
```
- name: BinPointer
  reference: Prior state-of-the-art binary pointer analysis tool (not open-sourced, see reference [24] in the original paper).
- name: BPA
  reference: Binary Pointer Analysis, an earlier program-analysis-based method (not open-sourced, see reference [23]).
- name: Callee
  reference: Deep-learning-based indirect call target predictor (model not publicly available, see reference [47]).
- name: SVF
  reference: Sparse flow-sensitive pointer analysis framework for source code LLVM IR (open-source, https://github.com/SVF-tools/SVF).
```

### Metrics
```
- name: Profiling-based precision (memory access targets)
  definition: Fraction of statically recovered memory access triples (instruction, block, offset) that match the targets observed during dynamic profiling with Intel Pin. TP / (TP + FP).
- name: Profiling-based recall (memory access targets)
  definition: Fraction of dynamically observed memory access triples that are correctly recovered by the analysis. TP / (total profiled triples).
- name: AICT (Average Indirect-Call Targets)
  definition: Mean number of possible call targets per indirect call site; lower values indicate higher precision.
- name: Profiling-based precision (indirect calls)
  definition: Fraction of statically predicted indirect call targets that correspond to the actual callee seen during execution (using Pin).
- name: Profiling-based recall (indirect calls)
  definition: Fraction of dynamically executed indirect calls whose target is correctly identified by the analysis.
- name: Execution time
  definition: Wall-clock time (in minutes) to complete the pointer analysis on a given binary.
- name: Memory usage
  definition: Peak memory consumption (in GB) during the analysis.
```

### Sub-questions
```
- RQ1: What is the profiling-based precision and recall of memory access target recovery compared to BinPointer?
- RQ2: How does the approach compare to BPA, BinPointer, Callee, and SVF on indirect call target recovery in terms of AICT and profiling-based precision/recall?
- RQ3: What are the execution time and memory consumption of the approach across the benchmark programs?
```

### Target Subject

Stripped x86-64 binary executables compiled from C programs with non-trivial pointer usage and indirect calls, including both synthetic benchmarks (SPEC CPU2006 C benchmarks like 403.gcc, 464.h264ref) and real-world server software (nginx, lighttpd, thttpd, etc.)

### Constraints

Binaries must be stripped of all debug symbols and compiled with GCC-9.2 at -O2. The analysis must operate directly on the binary without access to source code or intermediate representations. No dynamic or runtime information may be used during the analysis.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

SPEC CPU2006 requires a license and may not be freely distributable; the five open-source applications are freely available. Baseline tools BinPointer and BPA are not open-source, complicating direct comparison unless reimplemented. Callee’s trained model is missing from its repository. Implementing the analysis likely requires substantial development on top of Ghidra APIs (v11.0.1). Profiling with Intel Pin is feasible but adds engineering overhead. A server with at least 64 GB RAM and a 12-core CPU is recommended; execution times may range from minutes to several hours.

## Metadata

```
subfield: Program Analysis & Verification
venue: ISSTA 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```