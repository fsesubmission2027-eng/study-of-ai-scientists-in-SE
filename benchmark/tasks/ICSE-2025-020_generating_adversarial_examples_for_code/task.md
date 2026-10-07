# Task: ICSE-2025-020 — Generating Adversarial Examples for Code Models with High Success Rates and Low Query Costs

## Background

Deep Code Models are widely adopted for software engineering tasks such as vulnerability detection and code summarization, but they are vulnerable to adversarial attacks that apply semantic-preserving transformations like identifier substitution. Existing black-box attack methods based on identifier substitution are practical because they do not require model internals, yet they suffer from three critical limitations: they fail to fully utilise information from failed attack attempts, they often converge to suboptimal solutions due to local optima, and they face an inherent trade-off between attack success and the number of model queries. These shortcomings hinder their effectiveness and stealth in real-world settings, motivating the need for improved black-box attack techniques.

## Research Question

How can a black-box adversarial attack method for deep code models maximise attack success rate and minimise model invocations, while overcoming the feedback neglect, local optima, and efficiency issues that plague current identifier-substitution approaches?

## Experiment Setup

### Datasets
```
- name: Vulnerability Prediction Dataset
  source: https://github.com/microsoft/CodeXGLUE/tree/main/Code-Code/Vulnerability-Detection
  description: Standard dataset of C/C++ functions labelled as vulnerable or non-vulnerable, used for fine-tuning and evaluating vulnerability prediction models.
  access: open
- name: Clone Detection Dataset
  source: https://github.com/clonebench/BigCloneBench
  description: BigCloneBench dataset containing pairs of Java code fragments labelled as clones or non-clones, used for clone detection tasks.
  access: open
- name: Code Summarization Dataset
  source: https://github.com/github/CodeSearchNet
  description: CodeSearchNet Java dataset comprising method-level code snippets paired with natural language summaries, used for code summarisation.
  access: open
```

### Baselines
```
- name: ALERT
  reference: ALERT: An Attentive Black-Box Adversarial Attack on Code Models (arXiv:2105.14367)
- name: BeamAttack
  reference: BeamAttack: Perturbation-Priority Driven Black-Box Adversarial Attack on Code Models (reference [17])
```

### Metrics
```
- name: Attack Success Rate (ASR)
  definition: Percentage of test inputs for which an adversarial example is successfully generated, i.e., the model output changes after the semantic-preserving transformation.
- name: Total Generation Time (TGT)
  definition: Total wall-clock time required to complete the adversarial example generation process across all test inputs.
- name: Average Model Invocations (AMI)
  definition: Average number of queries to the victim model per successfully generated adversarial example.
- name: Average Running Time (ART)
  definition: Average time spent to successfully generate one adversarial example.
```

### Sub-questions
```
- RQ1: How do the attack methods compare in terms of attack success rate and efficiency (total generation time, average model invocations, average running time)?
```

### Target Subject

Pre-trained deep code models fine-tuned on three software engineering tasks: vulnerability prediction (binary classification), clone detection (binary classification), and code summarisation (natural language generation). Models include encoder-only (CodeBERT, GraphCodeBERT), encoder-decoder (CodeT5, PLBART), and decoder-only (CodeGPT) architectures.

### Constraints

The attack must be black-box with no access to model architecture, parameters, or gradients. Only identifier substitution transformations are permitted; other code transformations (e.g., structural changes) are excluded. The victim models are used as pre-trained and fine-tuned; no re-training or architectural changes are allowed during attack evaluation.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All datasets are publicly available from widely used repositories, and pre-trained model checkpoints can be obtained from platforms like Hugging Face. The evaluation runs each attack method on nine fine-tuned models across three tasks, requiring substantial GPU resources (e.g., an NVIDIA RTX 3090) and an estimated total execution time of several hundred GPU hours. The experiments involve many iterative model queries and are computationally intensive, but they can be conducted on a single machine with the specified hardware.

## Metadata

```
subfield: AI/ML System Testing
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```