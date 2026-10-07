# Task: ICSE-2025-018 — Automated Code Optimization: Overcoming the Limits of Single-Step Generation

## Background

Computational efficiency is critical for software quality, and performance bugs—inefficient code—can lead to increased latency and resource waste. Existing rule-based optimization tools have limited coverage and require manual effort, while recent large language models (LLMs) can generate optimized code but are typically limited to a single-step prompt. This one-step generation paradigm struggles to capture complex, combinatorial optimization patterns and fails to incorporate sufficient domain knowledge, often resulting in under-optimized code. Therefore, there is a need for more powerful methods that can explore a wider space of optimizations to achieve higher performance.

## Research Question

How can code optimization be improved beyond the current one-step generation paradigm using large language models?

## Experiment Setup

### Datasets
```
- name: PIE (Performance-Improving Edits)
  source: GitHub: [URL not specified in paper; see reference benchmark paper (PIE)]
  description: A benchmark derived from CodeNET, containing programming problems with slow and fast code pairs in Python and C++, along with public and private test cases (average 2.8 public and 95.9 private per problem).
  access: open
```

### Baselines
```
- name: Instruction Prompting
  reference: Directly prompts LLMs to generate optimized code without additional context.
- name: In-Context Learning (ICL)
  reference: Randomly selects a few slow-to-fast code pairs as examples in the prompt.
- name: Retrieval-Augmented Generation (RAG)
  reference: Uses BM25 to retrieve the most similar code from a training set and includes it in the prompt.
- name: Chain-of-Thought (COT)
  reference: Prompts LLM to first explain the optimization reasoning step-by-step before generating code, with manually crafted explanations for example pairs.
```

### Metrics
```
- name: Percent Optimized (OPT)
  definition: Fraction of test programs that are at least 10% faster and pass all private test cases.
- name: Speedup Rate (SP)
  definition: Average speedup (slow time / optimized time) over the entire test set, treating any incorrect or slower program as speedup 1.0.
```

### Sub-questions
```
- RQ1: How does the new approach compare with existing prompt-based methods in optimization rate and speedup?
- RQ2: What is the distribution of generated code in terms of correctness and speedup levels (e.g., correct, faster than slow, faster than human reference)?
- RQ3: How much does each component (e.g., sample selection, retrieval, prompting strategy) contribute to performance?
- RQ4: How do key hyperparameters (number of samples, maximum iterations) affect performance?
```

### Target Subject

Source code snippets in Python and C++ from the PIE benchmark that contain performance inefficiencies; the goal is to produce a functionally equivalent but faster version.

### Constraints

The method can access only the slow code and public test cases (input-output examples) during optimization. It must not use the human-written fast code or private test cases. The code must be executable in a standard environment (Python 3.9.12, GCC 9.4.0 with O3 flag). For reproducibility, the optimization process is limited to a fixed maximum number of iterations (4) and selected sample count (3). A Linux server with adequate CPU and GPU resources is required.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The PIE dataset is publicly available. Running LLM-based experiments requires access to powerful GPUs (e.g., A100 40GB) for open-source models like CodeLlama-34B, or paid API access for GPT-4 and Gemini. Full evaluation across four LLMs and multiple baselines necessitates significant compute time, potentially over 24 hours on a multi-GPU server. Consistently measuring execution times and filtering incorrect outputs are non-trivial technical challenges.

## Metadata

```
subfield: Compilers & Program Optimization
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```