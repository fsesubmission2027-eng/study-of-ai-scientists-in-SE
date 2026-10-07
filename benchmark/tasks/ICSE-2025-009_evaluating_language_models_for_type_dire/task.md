# Task: ICSE-2025-009 — Evaluating Language Models for Type-Directed Synthesis of Verified Programs

## Background

AI-assisted programming raises trustworthiness concerns, especially for critical software. Proof-oriented languages embed specifications and proofs, allowing fully verified implementations, but their use demands deep expertise and significant manual effort. While AI has been successfully applied to tactic-based proof assistants like Coq and Lean, automation for proof-oriented programming languages such as F* remains under-explored, largely due to a lack of large, curated datasets. A systematic, large-scale investigation is needed to understand the potential of language models to automate the construction of verified programs and proofs in these languages.

## Research Question

To what extent can language models, both large prompted models and fine-tuned smaller models, automatically generate correct verified implementations and proofs in a proof-oriented language from formal type specifications?

## Experiment Setup

### Datasets
```
- name: A corpus of F* programs and proofs extracted from 2,060 source files (approximately 600K lines of code) across 8 open-source projects, comprising around 32K top-level definitions, each posing a type-directed synthesis problem.
  source: GitHub: [URL to be provided – the dataset is publicly released alongside the paper]
  description: Each example consists of an F* top-level definition's type signature along with its surrounding file context. The goal is to generate the full definition (implementation + proof) that passes the F* type-checker.
  access: open
```

### Baselines
```
- name: Phi-2 (2.7B parameters)
  reference: Microsoft, 2023 (arXiv:2309.05463)
- name: StarCoder (15.5B parameters)
  reference: BigCode, 2023 (arXiv:2305.06161)
- name: GPT-3.5 (turbo)
  reference: OpenAI, 2023
- name: GPT-4
  reference: OpenAI, 2023
```

### Metrics
```
- name: verify@k
  definition: The proportion of problems for which at least one of k generated candidate definitions passes the F* type-checker (i.e., is semantically verified).
- name: Normalized edit distance
  definition: The minimum token-level Levenshtein distance between a verified generated solution and the ground truth, normalized by the number of tokens in the ground truth.
```

### Sub-questions
```
- RQ1: How does the performance of fine-tuned small language models compare to large prompted language models on type-directed program and proof synthesis in F*?
- RQ2: What is the individual contribution of file context, related examples, and premise selection to the success rate of definition synthesis?
- RQ3: What are the most frequent failure modes of language models on this task, and how do they relate to identifier hallucination and dataset overlap?
```

### Target Subject

Open-source F* projects covering domains such as cryptography, systems programming, and web security. Example project areas include verified TLS implementations, low-level parsers, and secure communication libraries.

### Constraints

Models are limited to generating a maximum of 2048 tokens per problem. Evaluation uses a strict train/test split at the file level to prevent information leakage. Solutions must be checked by the F* type-checker; only definitions passing the type-checker count as correct. No access to the ground-truth definition is allowed during generation.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The dataset and evaluation harness require a working F* toolchain, which is publicly available. Fine-tuning a 2.7B parameter model on the full dataset requires approx. 8-16 hours on a single A100 GPU. Evaluation involves repeated calls to the F* type-checker, making it CPU-intensive but parallelizable. While the main baselines are open-weight or accessible via API, reproducing the exact prompt preparations and retrieval augmentation details may require careful reimplementation based on paper descriptions.

## Metadata

```
subfield: Program Analysis & Verification
venue: ICSE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```