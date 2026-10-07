# Task: ISSTA-2025-007 — Assessing the Validity of Function-Level Vulnerability Detection Benchmarks

## Background

Machine learning for vulnerability detection (ML4VD) has become a rapidly growing research area, with the great majority of recent works defining the problem as a binary classification task at the function level: given only the code of a function, determine whether it contains a security vulnerability. However, in practice, whether a function makes a program vulnerable often depends on external context—such as how the function is called and whether inputs can reach a potentially unsafe operation. This context-dependency problem has long been recognized in static analysis and software testing but is largely overlooked in current ML4VD evaluation methodologies. As a result, the internal validity of benchmarking results in this field may be threatened, yet the prevalence and impact of context-dependent vulnerabilities in popular datasets remain unknown.

## Research Question

To what extent do context-dependent vulnerabilities and spurious feature correlations undermine the reliability of function-level machine learning for vulnerability detection?

## Experiment Setup

### Datasets
```
- name: BigVul
  source: https://github.com/ZJU-AutomatedSecurity/Big-Vul
  description: A dataset of C/C++ functions extracted from open-source projects, labeled as vulnerable or non-vulnerable based on patch commits and CVE reports.
  access: open
- name: Devign
  source: https://github.com/microsoft/Devign
  description: A dataset of C functions from two large open-source projects (FFmpeg and Qemu), with vulnerability labels derived from their commit history.
  access: open
- name: DiverseVul
  source: https://github.com/wagner-group/DiverseVul
  description: A recently published dataset of C/C++ functions from a broad range of open-source projects, covering many CWE types, with labels linked to CVEs and patch commits.
  access: open
```

### Baselines
```
- name: Gradient boosting on word counts
  reference: Use a classifier (e.g., XGBoost) trained solely on bag-of-words features extracted from function source code, ignoring code structure.
- name: Devign model
  reference: Zhou et al., "Devign: Effective Vulnerability Identification by Learning Comprehensive Program Semantics via Graph Neural Networks," NeurIPS 2019. GitHub: https://github.com/microsoft/Devign
- name: ReVeal model
  reference: Chakraborty et al., "ReVeal: A Deep Learning Approach to Vulnerability Detection," USENIX Security 2022. GitHub: https://github.com/VulDetProject/ReVeal
- name: BigVul model
  reference: Fan et al., "Big-Vul: A Large-Scale Vulnerability Dataset and a Code Representation for Vulnerability Detection," ISSTA 2020. GitHub: https://github.com/ZJU-AutomatedSecurity/Big-Vul
```

### Metrics
```
- name: Accuracy
  definition: Proportion of correctly classified functions (vulnerable or non-vulnerable).
- name: Precision
  definition: Proportion of predicted vulnerable functions that are truly vulnerable.
- name: Recall
  definition: Proportion of truly vulnerable functions that are correctly identified.
- name: F1-score
  definition: Harmonic mean of precision and recall.
- name: AUC-ROC
  definition: Area under the receiver operating characteristic curve, measuring overall ranking quality.
- name: Context-dependency rate
  definition: Percentage of functions for which vulnerability cannot be reliably determined without external calling context, as established by manual or automated analysis of patch commits and CVE descriptions.
- name: Cohen's Kappa
  definition: Inter-annotator agreement coefficient used to measure the reliability of manual labeling.
```

### Sub-questions
```
- RQ1: What percentage of functions in widely-used ML4VD datasets have vulnerability labels that depend on external context?
- RQ2: Can a simple classifier that ignores code structure achieve performance comparable to complex ML4VD models on these datasets?
- RQ3: What are the threats to the internal validity of current function-level ML4VD benchmarks?
```

### Target Subject

Functions extracted from C/C++ open-source projects, such as those from the Linux kernel, FFmpeg, Qemu, and others covered by the BigVul, Devign, and DiverseVul datasets.

### Constraints

All analyses must rely only on publicly available data (datasets, patch commits, CVE reports). Classification baselines must operate solely on the function source code without external context. Manual inspection of commits and CVEs may be required to establish ground truth for context dependency.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The datasets are publicly available and widely used. However, determining context dependency reliably typically requires manual review of patch commits and CVE reports, a labor-intensive process. Automated static analysis approaches could be explored but may introduce inaccuracies. The survey aspect requires access to published papers. Compute needs are modest for classification experiments, but human annotation effort is the main bottleneck.

## Metadata

```
subfield: Software Security
venue: ISSTA 2025
year: 2025
difficulty: hard
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```