# Task: FSE-2025-005 — Automated Porting of Security Patches Across Divergent Repository Branches

## Background

Modern software development often uses branching within repositories to manage features, but this practice can propagate vulnerabilities. When a parent branch is patched for a security flaw, other unfixed branches remain exposed unless the patch is manually ported—a slow, error-prone process due to inherent code divergences between branches. Existing automated patch porting tools either work at the hunk level, missing critical semantic context of the vulnerability, or use language models at the function level but still omit essential vulnerability-relevant statements and lack robust verification mechanisms. As a result, current approaches fail to reliably produce correct and complete patches across divergent branches, leaving vulnerabilities unmitigated.

## Research Question

How can an automated system correctly port security patches from a fixed branch to an unfixed branch, even when divergences prevent the patch from being directly applied?

## Experiment Setup

### Datasets
```
- name: CVE-based C repository patch porting dataset
  source: Constructed from NVD/CVE records and public GitHub commits using a four-step process: (1) collect CVE patches for C projects, (2) expand with additional commits matching edit distance or commit messages, (3) manually filter to function-level changes and pair earliest vs. latest patches per CVE, (4) split temporally (before/after 2023-08-23) into fine-tuning and evaluation sets. Contact authors for the processed dataset.
  description: Fine-tuning set: 2,842 CVEs with 4,618 function-level patch pairs. Evaluation set: 694 CVEs with 1,359 function-level patch pairs, each containing the original branch pre-patch and post-patch functions and the target branch vulnerable function and its human-written fix.
  access: constructable
```

### Baselines
```
- name: FixMorph
  reference: FixMorph (pattern-based patch porting, K. et al., 2018)
- name: TSBPORT
  reference: TSBPORT (semantic hunk types for porting, Z. et al., 2021)
- name: PPatHF
  reference: PPatHF (LLM-based function-level porting, Y. et al., 2023)
- name: GPT-3.5
  reference: OpenAI gpt-3.5-turbo
- name: GPT-4o
  reference: OpenAI GPT-4o
- name: CodeLlama (13B instruct)
  reference: CodeLlama 13B instruct-tuned, Hugging Face
- name: StarCoder (15.5B)
  reference: StarCoder 15.5B, BigCode project
```

### Metrics
```
- name: Exactly Match (E-M)
  definition: Count and percentage of generated patches that are character-by-character identical to the human-written target fix.
- name: Success (Succ)
  definition: Count and percentage of generated patches that are semantically equivalent to the human-written target fix (manual determination of functional equivalence).
- name: Failure (Fail)
  definition: Count and percentage of patches that are not semantically equivalent to the human fix.
- name: Code BLEU (C-B)
  definition: A code-aware variant of BLEU that measures token-level similarity (0–1) between a generated failed patch and the human fix, capturing partial correctness.
```

### Sub-questions
```
- RQ1: How effective is the approach at porting security patches compared to existing pattern-based and LLM-based baselines, in terms of function-level and CVE-level exact match, success rate, and Code BLEU?
```

### Target Subject

C language open-source projects with multiple branches that contain security vulnerabilities (CVEs), e.g., Linux kernel, OpenSSL, and other widely-used C repositories.

### Constraints

Only the original branch's pre-patch and post-patch functions and the target branch's vulnerable function are given as input; the ground-truth target fix is strictly for evaluation. No manual curation of sink functions, exploit test cases, or project-specific heuristics is allowed. Training and evaluation data must be split temporally (before/after August 2023) to prevent data leakage.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The dataset can be constructed from public CVE/NVD records and GitHub commits following a detailed four-step process, though it requires substantial manual filtering effort. Fine-tuning a 13B parameter LLM with LoRA on approximately 4,600 function pairs requires a GPU with at least 48GB memory (e.g., NVIDIA A100) and may take several hours. Inference evaluation is computationally lighter. A thorough comparison against seven baselines, including multiple LLMs, demands careful environment management.

## Metadata

```
subfield: LLM for Software Engineering
venue: FSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```