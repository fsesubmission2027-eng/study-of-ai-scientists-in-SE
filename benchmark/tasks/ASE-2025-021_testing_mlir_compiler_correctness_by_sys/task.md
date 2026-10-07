# Task: ASE-2025-021 — Testing MLIR Compiler Correctness by Systematically Exploring Lowering Paths

## Background

MLIR is a widely adopted compiler infrastructure that enables multi-level intermediate representations and reusable components. Its correctness is critical, as bugs in MLIR lowering passes can propagate to all downstream compilers. The MLIR lowering mechanism transforms high-level programs into low-level representations via configurable sequences of passes, and multiple valid lowering paths exist for the same program. An inherent property is that all valid paths should produce semantically equivalent results. Current testing techniques for MLIR typically rely on a single, predefined lowering path per program, missing bugs that appear only under alternative valid pass sequences. There is a gap in systematic exploration of the diverse lowering space to uncover such hidden correctness issues.

## Research Question

How can a testing approach effectively explore diverse valid lowering paths for MLIR programs to detect correctness bugs such as miscompilations and crashes?

## Experiment Setup

### Datasets
```
- name: TOSA dialect program generator
  source: [NOT SPECIFIED IN PAPER]
  description: Generates valid MLIR programs in the TOSA high-level dialect that can be lowered through various pass combinations.
  access: restricted
- name: Ratte program generator
  source: Available from the Ratte tool repository (see baseline reference)
  description: Generates programs covering arith, linalg, and tensor dialects, with expected semantic outputs for correctness checking.
  access: open (if Ratte artifact is publicly available)
```

### Baselines
```
- name: Ratte
  reference: Ratte tool (state-of-the-art MLIR testing technique that generates programs with semantic expectations and uses a predefined fixed lowering path; original publication artifact may be on GitHub)
```

### Metrics
```
- name: Number of detected bugs
  definition: Total count of previously unknown bugs confirmed or fixed by MLIR developers, with crashes deduplicated by assertion and stack trace, and miscompilations by the faulty pass.
- name: Lowering success rate
  definition: Ratio of test programs that are successfully lowered and executed within the maximum allowed lowering steps.
- name: Dialect coverage
  definition: Number of distinct MLIR dialects (e.g., tosa, linalg, arith, tensor) exercised by the lowering paths during testing.
- name: Operation coverage
  definition: Number of distinct MLIR operations (within dialects) executed by the test programs.
- name: Line coverage
  definition: Percentage of lines in the MLIR source code that are executed during testing.
- name: Branch coverage
  definition: Percentage of conditional branches in the MLIR source code that are taken.
```

### Sub-questions
```
- RQ1: To what extent can exploration of diverse lowering paths detect previously unknown miscompilations and crashes in MLIR?
- RQ2: How does path-exploration testing compare to fixed-path testing (Ratte) in bug detection and coverage?
- RQ3: How do stepwise construction and priority-based scheduling contribute to the ability to produce successful lowering paths?
```

### Target Subject

The MLIR compiler infrastructure within the LLVM project, specifically the lowering passes that transform programs from high-level dialects (e.g., TOSA) to low-level dialects (e.g., LLVM IR) via intermediate dialects such as linalg, arith, and tensor. Examples include upstream MLIR revision commits and dialects like tosa, linalg, tensor, arith.

### Constraints

MLIR revision range for bug-finding experiments: commits 0a44b24 to ba63150. Fixed version for comparison: 449e2f5. Maximum lowering attempts per program: 30 steps. Time budget per input program: 30 minutes. Operation priority initialised to 10 with penalty of 1 for failed conversions. Each 12-hour experiment repeated 5 times. Hardware: Intel Xeon Gold 6354 CPU, 500 GB RAM, Ubuntu 20.04. The method must not rely on human-written test programs; inputs must be generated or provided by existing generators.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

TOSA program generator must be implemented from scratch or a similar high-level dialect generator used; Ratte's generator is presumably open-source. Building MLIR from LLVM source requires a large build environment and compilation time. Running meaningful fuzzing campaigns demands hours to days of compute; the study's 12-hour repeated runs suggest significant resource needs. Coverage measurement requires instrumenting MLIR, which is straightforward. Main challenge is constructing diverse valid MLIR programs that exercise obscure lowering paths, especially for dialects without existing generators.

## Metadata

```
subfield: Compilers & Program Optimization
venue: ASE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```