# Task: FSE-2025-011 — Efficient Compiler Auto-Tuning for Optimization Flag Selection

## Background

Compilers translate high-level code into machine code, providing numerous optimization flags (e.g., -floop-unroll-and-jam, -fdce) to improve runtime performance or code size. For a given program, choosing a near-optimal combination of flags (an optimization sequence) is challenging because of the exponential number of possible flag combinations. Manually tuning flags is infeasible, so automatic compiler auto-tuning techniques have been proposed. Most existing techniques treat flag selection as a search problem, exploring the full optimization space using strategies like genetic algorithms or reinforcement learning. However, due to the vast space, exploration is time-consuming and often yields only modest improvements over default settings. A promising direction is to reduce the search space so that exploration can be more efficient while still discovering high-performance sequences.

## Research Question

How can compiler auto-tuning efficiently select optimization flag sequences that achieve better runtime performance than default compiler optimization levels, given a limited time budget?

## Experiment Setup

### Datasets
```
- name: cBench
  source: https://github.com/ctuning/ctuning-programs
  description: A collection of 28 C programs with varying computational characteristics, ranging from 100 to 26,000 lines of code.
  access: open
- name: PolyBench
  source: https://sourceforge.net/projects/polybench/
  description: A benchmark suite of 30 computational kernels for polyhedral optimization, written in C.
  access: open
```

### Baselines
```
- name: RIO
  reference: Random Iterative Optimization (RIO) [14]
- name: CFSCA
  reference: Critical Flag Selection for Compiler Auto-tuning (CFSCA) [39]
- name: CompTuner
  reference: Compiler Auto-tuning via Multiple-Phase Learning (CompTuner) [40]
- name: SRTuner
  reference: State-of-the-art compiler auto-tuning through interaction (SRTuner) [33]
```

### Metrics
```
- name: Speedup ratio over -O3
  definition: (execution_time_O3 - execution_time_selected) / execution_time_selected * 100%. A higher value indicates better runtime performance.
```

### Sub-questions
```
- RQ1: How does the runtime performance improvement of the auto-tuning technique compare to the baseline techniques across different time budgets?
- RQ2: How do different design choices within the auto-tuning technique affect its overall effectiveness?
```

### Target Subject

C programs from cBench (28 programs) and PolyBench (30 programs) benchmarks, with varying code size and computational patterns, running on GCC 13.1.0.

### Constraints

The search time budget per program is limited to 1250, 2500, and 5000 seconds. Each technique is executed 5 times per program to account for randomness, and the median speedup is reported. The compiler used is GCC 13.1.0. Experiments are conducted on a workstation with Intel Xeon CPU E5-2680 v4, 251GB RAM, Ubuntu 18.04.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

Both benchmarks are publicly available and widely used. Reproducing the full experiment requires extensive compilation and execution runs; each technique-program-budget combination requires multiple runs, totaling hundreds of invocations. With 58 programs, 4 baselines, and 3 budgets, the total experiment may require several days of compute time on a powerful workstation. The environment needs GCC 13.1.0 and a Linux system. Randomness in the auto-tuning process increases the computational burden.

## Metadata

```
subfield: Compilers & Program Optimization
venue: FSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```