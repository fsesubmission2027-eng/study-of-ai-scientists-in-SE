# Task: ICSE-2025-011 — Improving Coq Proof Automation with Project-Specific Proof Examples

## Background

Poor software quality imposes massive economic costs, and formal verification using proof assistants like Coq can mathematically guarantee correctness. However, writing proofs manually requires significant expertise and effort. Recent work has explored using machine learning and large language models (LLMs) to automatically generate proofs, often by retrieving relevant lemmas and definitions. However, existing approaches do not fully leverage the local proof patterns and similar proofs available within the same project, which limits their ability to adapt to a project’s specific proof strategies and evolving proof states.

## Research Question

What is the effect of augmenting a language model’s context with similar proofs from the current project on the ability to automatically generate Coq proofs?

## Experiment Setup

### Datasets
```
- name: CoqStoq
  source: https://github.com/rkthomps/coq-modeling
  description: A corpus of 196,929 theorems and 2,225,515 proof steps extracted from 2,226 open-source Coq GitHub repositories, split into a training set and an evaluation benchmark of 12 well-maintained projects.
  access: open
```

### Baselines
```
- name: Proverbot9001
  reference: Sanchez-Stern et al., 2020 (paper name not given in prompt)
- name: Tactician
  reference: Blaauwbroek et al., 2020
- name: Graph2Tac
  reference: Blaauwbroek et al., 2024
```

### Metrics
```
- name: Theorem proven count
  definition: The number of theorems for which a syntactically valid proof script is generated within a 10-minute timeout, aggregated across all benchmark projects.
```

### Sub-questions
```
- RQ1: How does the proof success rate compare between the proposed approach and existing proof synthesis tools?
- RQ2: How much do a proof retriever and a lemma retriever contribute to the overall success?
- RQ3: How do alternative retrieval methods affect proof synthesis performance?
- RQ4: How does the approach perform when a naïve retrieval algorithm is used instead of the learned retriever?
- RQ5: How does rollout search compare to best-first search in terms of proof success?
- RQ6: What types of theorems can the approach prove and how do the generated proofs compare to those of other tools?
```

### Target Subject

Coq proof synthesis tools evaluated on a benchmark of real-world Coq projects, including examples such as the CompCert C compiler and maintained libraries from the Coq Community repository.

### Constraints

Evaluation must use Coq 8.18. Each theorem attempt is limited to a 10-minute timeout, not counting file loading and compilation. Inference should run on a single NVIDIA RTX 2080 GPU and a single CPU with 16GB RAM. The language model is fine-tuned on the CoqStoq training set; it is a 1.3B parameter decoder-only model for which the pretraining cutoff occurred before the benchmark projects were created.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The CoqStoq dataset and all code are publicly available on GitHub. Training the language model requires 4 NVIDIA A100 GPUs and approximately 60,000 steps, which may be resource-intensive. Inference and evaluation on the benchmark are feasible with a single consumer GPU. The benchmark contains 10,396 theorems across 12 projects, and running all baselines may require additional setup (e.g., Coq 8.11 for Graph2Tac).

## Metadata

```
subfield: Program Analysis & Verification
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```