# Task: ASE-2025-020 — Localizing Vulnerable Code Regions to Improve Automated Detection

## Background

Software vulnerabilities can have severe consequences, motivating automated detection methods. Pre-trained Language Models (PLMs) fine-tuned on function-level code have shown promise, but they typically process entire functions uniformly without highlighting which parts are vulnerable. This often dilutes critical signals, as vulnerabilities often originate from localized code segments. Existing methods lack explicit guidance on where the model should focus, making it harder to learn vulnerability patterns effectively during training.

## Research Question

How can a PLM-based vulnerability detector be guided to focus on critical code regions without explicit vulnerability location annotations?

## Experiment Setup

### Datasets
```
- name: Devign
  source: https://github.com/microsoft/CodeXGLUE/tree/main/Code-Code/Defect-detection
  description: Function-level C/C++ code snippets from FFmpeg and QEMU annotated with binary vulnerability labels. Filtered to 19,771 samples using UniXcoder tokenizer (512-token limit).
  access: open
- name: Big-Vul
  source: https://github.com/ZeoVan/MSR_20_Code_Vulnerability_CSV_Dataset
  description: Large-scale dataset of C/C++ functions from 348 GitHub repositories with CWE ID labels. Only vulnerable functions retained, resulting in 6,924 instances across 36 CWE categories after filtering (512-token limit).
  access: open
- name: PrimeVul
  source: https://github.com/PrimeVul/PrimeVul
  description: Paired dataset of vulnerable and patched function pairs from open-source C/C++ projects. No additional filtering applied (paired version used).
  access: open
```

### Baselines
```
- name: UniXcoder (base-9, fine-tuned)
  reference: UniXcoder model: microsoft/unixcoder-base-nine
- name: CodeT5+ (encoder-only 220M)
  reference: CodeT5+ model: Salesforce/codet5p-220m
- name: Roberta-based PLM (e.g., CodeBERT)
  reference: CodeBERT model: microsoft/codebert-base
- name: CSLS
  reference: CSLS (Code Semantic Learning with Statement-Level Supervision, referenced as [36])
- name: AIBugHunter
  reference: AIBugHunter (referenced as [43])
```

### Metrics
```
- name: Accuracy (binary detection)
  definition: Fraction of correctly predicted vulnerable/non-vulnerable functions.
- name: Weighted F1-score (classification)
  definition: Weighted average of per-class F1-scores, weighted by the number of samples in each CWE class.
- name: Top-N Accuracy (line localization)
  definition: Percentage of samples where the ground-truth modified line is among the top-N lines ranked by predicted importance.
- name: Line-level F1-score
  definition: Harmonic mean of precision and recall for identifying modified lines.
- name: Pair-wise accuracy
  definition: Accuracy on vulnerable-patch pairs, treating each pair as a single evaluation unit (correct only if both vulnerable and patched versions are correctly classified).
```

### Sub-questions
```
[NOT SPECIFIED IN PAPER]
```

### Target Subject

C/C++ function-level code from open-source projects (e.g., FFmpeg, QEMU, and various GitHub repositories) with annotated vulnerability types or binary labels, used for vulnerability detection and classification tasks.

### Constraints

Input functions must be tokenized with UniXcoder (with 512 or 1024 token limits). Functions must contain at least one modifiable line within the token limit; those without are excluded. Training uses only function-level vulnerability labels, no line-level vulnerability annotations. Random seed fixed to 123456 for reproducibility.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All three datasets are publicly available (Devign via CodeXGLUE, Big-Vul on GitHub, PrimeVul from its dedicated repository). Fine-tuning PLMs requires a GPU (e.g., a single NVIDIA A100 or V100), with total training time estimated at under 12 hours for all experiments. Preprocessing and filtering scripts need to be implemented to replicate the dataset splits and token-length filtering.

## Metadata

```
subfield: Software Security
venue: ASE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```