# Task: ASE-2025-007 — Context-Aware Repair of Flaky Tests in Industrial Go Monorepos

## Background

Flaky tests—tests that nondeterministically pass or fail on unchanged code—are a major source of wasted developer effort and delayed releases in large-scale software development. In many organizations, any test failure can block deployment until resolved, forcing investigation of failures that may not indicate real bugs. Recent advances in large language models (LLMs) have shown promise for automatically repairing flaky tests, but existing LLM-based tools (e.g., FlakyDoctor) have been successful only on open-source projects and fail in industrial settings. These failures arise primarily from a context problem: providing only the test code misses critical production-code information necessary for root cause analysis, whereas providing the entire repository (often >100K LOC) overwhelms the model and degrades reasoning. As a result, there is a need for approaches that automatically identify and supply only the most relevant code context to the repair model while also generating comprehensible root cause explanations for developers.

## Research Question

How can a flaky-test repair system provide LLMs with just enough context from a large codebase to repair flaky tests and explain root causes without overwhelming the model?

## Experiment Setup

### Datasets
```
- name: Uber Go monorepo flaky tests
  source: Private industrial repository (not publicly available)
  description: A dataset of 1,115 real-world flaky tests collected over six months from a monorepo containing over 100 million lines of Go code across 100+ projects, covering categories such as schedule randomness, non-deterministic iteration, timestamp discrepancies, shared state pollution, and time-dependent flakiness. Each test has a recorded failing run.
  access: restricted
```

### Baselines
```
- name: FlakyDoctor
  reference: Prior work on LLM-based flaky test repair (see [6] in the original paper)
- name: Agentless
  reference: Prior context collection approach for code tasks (see [11] in the original paper)
- name: AutoCodeRover
  reference: Prior context collection approach for code tasks (see [12] in the original paper)
- name: RepoGraph
  reference: Prior graph-based context collection approach (see [13] in the original paper)
```

### Metrics
```
- name: Repair Success Rate
  definition: The percentage of flaky tests for which the tool produces a patch that eliminates flakiness (the test passes consistently on extensive reruns).
- name: Developer Acceptance Rate
  definition: The percentage of generated fixes that developers accept and merge into the codebase.
```

### Sub-questions
```
- RQ1: How effective is the proposed approach at automatically repairing flaky tests in an industrial monorepo?
- RQ3: How does the proposed approach compare with existing state-of-the-art LLM-based flaky test repair and context collection methods?
- RQ5: How do developers perceive the usefulness of the repairs and root cause explanations produced by the approach?
```

### Target Subject

Industrial-scale Go monorepos with table-driven tests, concurrent code, and complex production code dependencies. Examples include monorepos at large technology companies like Uber or Google.

### Constraints

Repair attempts must complete within 2 hours per flaky test. The approach must not require pre-classification of flaky test types; only test failure information is available. The method must produce an automatically applicable patch and a root cause explanation. LLM access is limited to the test code and the context selected by the approach; no manual intervention. Test re-execution (e.g., 1000 runs) is needed to confirm a fix. Go code with table-driven testing patterns must be handled.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The evaluation dataset is a private industrial monorepo and is not publicly accessible, making replication difficult without similar internal data. Compute requirements include running each test up to 1000 times to capture flaky failures and invoking LLM APIs for context selection and patch generation, which can be slow and costly. The full evaluation spanned six months; achieving comparable diversity of flaky test types requires sustained access to a large, active codebase.

## Metadata

```
subfield: Automated Testing & Test Generation
venue: ASE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```