# Task: ICSE-2025-002 — Evaluating Assisting Exploration Strategies for Grey-Box Fuzzing on Real-World Programs

## Background

Grey-box fuzzers generate inputs to maximize code coverage using lightweight instrumentation feedback, but they often fail to explore program states guarded by complex constraints such as equality checks. Various assisting exploration strategies—dictionary-based token insertion, input-to-state correspondence, SMT solving, and gradient-based solving—have been proposed to overcome this limitation. However, these strategies have been evaluated under differing protocols, using inconsistent benchmarks and time budgets, and there is little understanding of the specific types of program states each strategy can explore. A rigorous, uniform comparison is needed to assess the true effectiveness and limitations of these strategies and to inform future improvements.

## Research Question

How effective are existing assisting exploration strategies for grey-box fuzzers when compared on a common benchmark, and what distinguishes the specific program states they manage to explore?

## Experiment Setup

### Datasets
```
- name: Fuzzing evaluation benchmark (21 real-world programs)
  source: [Artifact repository URL] containing the list and construction scripts
  description: 21 open-source C/C++ programs commonly used in fuzzing research, covering 10 file formats (e.g., ELF, XML, JPEG, JSON), code sizes from ~2K to >150K LoC, and diverse functionalities including development tools, image/network processing, and XML tools.
  access: constructable
```

### Baselines
```
- name: AFL
  reference: https://lcamtuf.coredump.cx/afl/
- name: AFL++
  reference: https://github.com/AFLplusplus/AFLplusplus
- name: MOpt-AFL
  reference: https://github.com/puppet-meteor/MOpt-AFL
- name: FairFuzz
  reference: https://github.com/carolemieux/FairFuzz
- name: QSYM
  reference: https://github.com/sslab-gatech/qsym
- name: MEUZZ
  reference: https://github.com/Fuzzers/meuzz
- name: Pangolin
  reference: https://github.com/pangolin-fuzzer/Pangolin
- name: Angora
  reference: https://github.com/AngoraFuzzer/Angora
- name: REDQUEEN (AFL++ redqueen mode)
  reference: https://github.com/AFLplusplus/AFLplusplus
```

### Metrics
```
- name: Edge coverage
  definition: Number of distinct control-flow transitions (edges between basic blocks) covered during fuzzing, as measured by AFL's afl-showmap tool.
```

### Sub-questions
```
- RQ1: How does the code coverage achieved by fuzzers with different assisting exploration strategies compare when evaluated on a uniform benchmark under equal time budgets?
- RQ2: What specific types of program states (e.g., equality constraints, complex branch conditions) are explored by each strategy, and how do they differ?
```

### Target Subject

AFL-based grey-box fuzzers augmented with various assisting exploration strategies, including dictionary-based (AFL, AFL++, MOpt, FairFuzz with dictionary mode), SMT-solver-based (QSYM, MEUZZ, Pangolin), gradient-based (Angora), and input-to-state-correspondence-based (REDQUEEN). All are evaluated on the same set of open-source programs.

### Constraints

All fuzzers must be AFL-based and instrument programs using AFL's LLVM-mode (LLVM-13). The dictionary-based fuzzers must use automatically generated dictionaries via tools like FuzzingDriver to avoid manual bias. Each fuzzer runs for exactly 24 hours per trial, with 5 independent repetitions, starting from a standard seed corpus. Experiments must be conducted on identical hardware and OS (e.g., Ubuntu 18.04, 128-core AMD server) to ensure comparability.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All benchmark programs and fuzzer implementations are publicly available, enabling reproduction. However, a full-scale evaluation across 21 projects and 9+ fuzzer configurations for 24 hours each, repeated 5 times, requires hundreds of CPU-hours and a high-core-count server. The manual analysis of explored program states (RQ2) is time-intensive and demands expertise in binary analysis and constraint identification. Setting up and compiling all fuzzers with LLVM-13 may involve compatibility issues.

## Metadata

```
subfield: Fuzzing & Vulnerability Detection
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```