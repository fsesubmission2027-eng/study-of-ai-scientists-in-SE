# Task: ICSE-2025-007 — A Benchmark for Evaluating LLM Code Generation on Unfamiliar Real-World Code

## Background

Large language models (LLMs) have shown impressive code generation abilities, but existing benchmarks often overestimate their performance because they test code that may have been encountered during training. Three critical gaps cause this bias: (1) the target code appears in the training set, (2) benchmark cases become stale as models are retrained, and (3) realistic project-level dependencies are not provided. These factors lead to a 'Specialist in Familiarity' problem where models excel on known code but fail on genuinely unseen tasks. A new evaluation benchmark is needed that addresses these gaps by testing LLMs on code unlikely to have been memorized, while providing a realistic development context.

## Research Question

How to design a benchmark that faithfully evaluates the code generation capabilities of LLMs on unfamiliar code, avoiding inflated performance due to training data exposure, and reflecting real-world software development constraints?

## Experiment Setup

### Datasets
```
- name: Unfamiliar-Code Eval Benchmark
  source: Constructable via the following procedure: (i) select highly starred GitHub projects; (ii) extract functions introduced after a known LLM training cutoff date and covered by official test suites; (iii) automatically transform the code to reduce familiarity while preserving functionality (e.g., renaming identifiers, restructuring code, altering syntactic patterns); (iv) collect surrounding contextual dependencies (some necessary, some irrelevant) to simulate partial dependency knowledge.
  description: 1,354 functions from 5 real-world projects, each with functional descriptions, corresponding code, and curated dependencies; designed to be entirely regeneratable with different transformations to avoid staleness.
  access: constructable
```

### Baselines
```
- name: HumanEval
  reference: https://github.com/openai/human-eval
- name: MBPP
  reference: https://github.com/google-research/google-research/tree/master/mbpp
- name: APPS
  reference: https://github.com/hendrycks/apps
- name: CodeXGLUE
  reference: https://github.com/microsoft/CodeXGLUE
```

### Metrics
```
- name: Compile Pass Rate (CPR@5)
  definition: Fraction of generated code snippets that compile successfully when substituted into the original project, averaged over 5 independent generations per function.
- name: Test Pass Rate (TPR@5)
  definition: Fraction of generated code snippets that pass the associated official system tests, using pass@5 to reduce variance.
```

### Sub-questions
```
- RQ1: How do LLMs perform on the constructed benchmark compared to traditional code generation benchmarks?
- RQ2: How do different transformation strategies (varying levels of code unfamiliarity) impact LLM performance?
- RQ3: What types of defects are common in LLM-generated code that passes compilation but fails functional testing?
```

### Target Subject

General-purpose and code-specialized large language models for code generation, e.g., GPT-3.5, GPT-4, DeepSeek-Coder.

### Constraints

The benchmark must ensure the evaluated code was not part of any known training set for the target LLMs; it must provide only partial, realistic dependency context (not all dependencies explicitly given); and the entire benchmark must be re-generatable (e.g., through re-application of transformation rules) to prevent staleness over time.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

Mining GitHub projects for candidate functions and their test integration requires substantial infrastructure and careful date filtering. Building a Docker-based execution environment for each project to compile and test generated code is resource-intensive and may need customized setups per project. The code transformation step demands robust program analysis and rewriting tools to modify code without altering functionality, which can be technically challenging, especially for complex language constructs.

## Metadata

```
subfield: LLM for Software Engineering
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```