# Task: FSE-2025-006 — Automated Detection of Unconfirmed Statistical Assumptions in Data Science Notebooks

## Background

Data analysis is central to many scientific and business domains, with languages like Python and R providing a rich ecosystem of statistical methods accessible via literate programming notebooks. Most statistical functions (e.g., t-tests, ANOVA, linear regression) rely on probabilistic assumptions about the data, such as normality, equal variance, or independence. However, in practice, data analysts rarely check whether these assumptions hold, often due to lack of awareness or tool support. Current notebook environments do not offer automated mechanisms to verify these assumptions when statistical methods are called, leaving analysts to either ignore them or perform ad-hoc checks. This gap leads to widespread potential misuses of statistical methods, where conclusions may be invalid even if the code runs without errors. There is a need for an approach that can systematically and automatically assess whether the required assumptions are met whenever a statistical function is invoked in a notebook.

## Research Question

How can unconfirmed statistical assumptions be automatically detected in data analysis notebooks, and what is the prevalence and practical impact of such unconfirmed assumptions in real-world notebooks?

## Experiment Setup

### Datasets
```
- name: Kaggle Notebook Corpus (statistical functions)
  source: Kaggle Kernels: search via Kaggle API for notebooks referencing a pre-defined set of statistical function names; manually filter for executability, public data, and runtime under 10 minutes; clone to preserve the execution environment.
  description: A corpus of 128 publicly available Kaggle notebooks (Jupyter and R Markdown) that call common hypothesis testing and regression functions from scipy.stats (Python) and stats (R). Each notebook was manually validated to ensure it contains actual calls, uses non-private data, runs without non-trivial errors, and completes in under 10 minutes.
  access: constructable
```

### Baselines
```
[NOT SPECIFIED IN PAPER]
```

### Metrics
```
- name: Annotation count
  definition: Number of individual assumption annotations needed to encode the statistical assumptions for a standard set of hypothesis testing and regression functions.
- name: Unconfirmed assumption warnings
  definition: Number of calls to annotated statistical functions where the automated check rejects the assumption hypothesis at a significance level of 0.05.
- name: Potential misuse call sites
  definition: Number of unique call sites in the notebooks that exhibit at least one unconfirmed assumption.
- name: Significant misuse calls
  definition: Number of calls to hypothesis test functions where the p-value of a more appropriate alternative test (selected based on which assumptions are confirmed) would fall on a different side of the chosen significance level α than the p-value of the original test, thus leading to a different conclusion.
- name: Runtime overhead factor
  definition: Ratio of mean execution time of a function with assumption checking to mean execution time without checking, measured on synthetic random samples.
```

### Sub-questions
```
- RQ1: How many annotations are required to encode statistical assumptions for a predefined set of common hypothesis testing and regression functions?
- RQ2: What proportion of statistical function calls in real-world notebooks exhibit at least one unconfirmed assumption?
- RQ3: Among hypothesis test calls with unconfirmed assumptions, how many would lead to a different conclusion if a more appropriate statistical test were used?
```

### Target Subject

Jupyter and R Markdown notebooks that employ hypothesis testing and linear regression functions (e.g., t-tests, ANOVA, linear regression) from data science libraries such as scipy.stats in Python and stats in R.

### Constraints

The approach must not require manual inspection or modification of notebooks by data analysts; assumption checking must be triggered automatically when statistical functions are called. The assumption definitions should be provided once per statistical function and applied universally. The checking must not alter the output of the original statistical function (e.g., only emit warnings). The significance level for assumption checks should be configurable (default 0.05). Runtime overhead must be measured and remain acceptable for interactive use.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

Kaggle notebooks are publicly accessible through the Kaggle API; a similar corpus to the one used in the motivating study can be constructed by querying for specific function names, though manual validation (filtering for executable, non-private notebooks) is labor-intensive but replicable. Each notebook runs in under 10 minutes on Kaggle's standard hardware, so full evaluation of ~128 notebooks can be completed within a day on a single machine. No GPU is required. The main technical challenge is preserving the correct execution environment (snapshotted Kaggle kernels) to avoid dependency errors.

## Metadata

```
subfield: Program Analysis & Verification
venue: FSE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```