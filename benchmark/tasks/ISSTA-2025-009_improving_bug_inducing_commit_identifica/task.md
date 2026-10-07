# Task: ISSTA-2025-009 — Improving Bug-Inducing Commit Identification with Commit Message Analysis and Patch Context

## Background

The SZZ algorithm and its variants are widely used for identifying bug-inducing commits from bug-fixing commits, but they suffer from low precision. Existing approaches overlook commit messages, assume only deleted lines cause bugs, ignore unmodified lines in the patch context, and rely on heuristic candidate selection. While a deep learning-based variant improves precision, it sacrifices recall and requires complex preprocessing. These limitations lead to many false positives and missed detections, especially for bug-fixing commits that only add lines. Addressing these gaps is essential for more accurate software quality analysis and defect prediction.

## Research Question

How can bug-inducing commits be accurately identified from bug-fixing commits without relying solely on deleted lines or heuristics, by leveraging commit messages and full patch context?

## Experiment Setup

### Datasets
```
- name: DS_LINUX
  source: Contact authors of Lyu et al. (2021) dataset
  description: 76,046 pairs of bug-fixing and bug-inducing commits from the Linux kernel, annotated by developers via commit messages.
  access: open
- name: DS_GITHUB
  source: Contact authors of Rosa et al. (2021) dataset
  description: Bug-fixing and bug-inducing commit pairs from hundreds of GitHub repositories in C and Java, annotated by developers.
  access: open
- name: DS_APACHE
  source: Contact authors of Wen et al. (2022) dataset
  description: Bug-fixing and bug-inducing commit pairs from several high-star Apache projects, annotated via bug reports and commit messages.
  access: open
```

### Baselines
```
- name: B-SZZ
  reference: Rosa et al. replication package (SZZ Unleashed)
- name: AG-SZZ
  reference: Rosa et al. replication package
- name: MA-SZZ
  reference: Rosa et al. replication package
- name: L-SZZ
  reference: Rosa et al. replication package
- name: R-SZZ
  reference: Rosa et al. replication package
- name: RA-SZZ
  reference: Rosa et al. replication package
- name: NeuralSZZ
  reference: Tang et al. replication package (trained on original training set)
```

### Metrics
```
- name: Precision
  definition: Fraction of identified bug-inducing commits that are actually bug-inducing.
- name: Recall
  definition: Fraction of actual bug-inducing commits that are correctly identified.
- name: F1-score
  definition: Harmonic mean of precision and recall.
```

### Sub-questions
```
- RQ1: How effective is the proposed approach compared to existing SZZ variants in terms of precision, recall, and F1-score?
- RQ2: What is the contribution of individual components (e.g., commit message analysis, patch context) to the overall performance?
- RQ3: How does performance vary when employing different underlying models for analysis?
```

### Target Subject

C and Java open-source software projects with developer-annotated bug-fixing and bug-inducing commits. Examples include the Linux kernel, various GitHub repositories, and Apache projects such as HTTP Server and Tomcat.

### Constraints

The method must only use information from the bug-fixing commit's patch, commit message, and historical commit data from the version control system. Issue tracker or bug report information beyond the commit message is not allowed. Evaluation must use the same combined dataset and a random sample of 1,500 commits from DS_LINUX (95% confidence, 5% margin) to ensure fair comparison. The NeuralSZZ baseline must be trained on its original training set. Evaluation runs should be repeated three times to mitigate randomness.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All three datasets are publicly available from prior work, though obtaining them may require contacting authors. Running baselines involves executing multiple SZZ implementations on large repositories, which can take hours. NeuralSZZ training and application may require a GPU. Any approach that uses large language models will need either API access (e.g., OpenAI) or local GPU resources (e.g., NVIDIA A800) to run models like Llama-3-8B. The total evaluation, including sampling and comparison, is computationally intensive but feasible on a modern server.

## Metadata

```
subfield: Software Maintenance & Evolution
venue: ISSTA 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```