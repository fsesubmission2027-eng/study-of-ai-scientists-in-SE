# Task: ICSE-2025-022 — Assessment of Inappropriate Entity Collocation and Separation in Software Modules

## Background

Software modularity is a key quality attribute that affects reusability and maintainability. However, maintaining an optimal modular structure is challenging as systems evolve. Current approaches either propose comprehensive remodularization plans that require extensive code changes, or detect module-level design issues (e.g., cycles) that are too coarse to guide specific refactoring actions. There is a lack of fine-grained architectural smells that can pinpoint individual entity pair misplacements—pairs that should be collocated but are separated, or vice versa—which would offer more actionable guidance. This work investigates the extent, impact, and evolution of such inappropriate modular relationships (termed PairSmell) in real-world software.

## Research Question

To what extent do inappropriate modular relationships (entity pairs that are inaptly separated or collocated) manifest in open-source software projects, how do they affect maintenance indicators such as co-change, and how do they persist over time?

## Experiment Setup

### Datasets
```
- name: 20-Project PairSmell Dataset
  source: Replication package provided by the original study authors (public repository)
  description: Snapshot data of 20 C/C++ and Java GitHub projects with >2 years history, >1000 commits, >100 entities, including dependency graphs and commit histories.
  access: open
```

### Baselines
```
[NOT SPECIFIED IN PAPER]
```

### Metrics
```
- name: Percentage of affected entities/pairs
  definition: Proportion of entities (or pairs) involved in at least one smell instance relative to total entities/pairs.
- name: Smell density
  definition: Average number of smell instances per affected entity.
- name: Commit Overlap Rate (COR)
  definition: |Cmt_i ∩ Cmt_j| / |Cmt_i ∪ Cmt_j|, measuring overlap of commit sets between two entities.
- name: Code Change Overlap (CCO)
  definition: Lines of code changed together in same commits relative to total lines changed for each entity, computed as |Ch_i,j|/(|Ch_i|+|Ch_j|).
- name: Developer Overlap Rate (DOR)
  definition: 2*|Dev_i,j|/(|Dev_i|+|Dev_j|), measuring developer set overlap.
- name: Relative co-change factor (K_COR, K_CCO, K_DOR)
  definition: Ratio of average metric value for smelly pairs over non-smelly pairs, indicating co-change disparity between inappropriate and properly modularized pairs.
```

### Sub-questions
```
- RQ1: How prevalent are inappropriate separated (InSep) and inappropriate collocated (InCol) pairs across software projects?
- RQ2: How do InSep and InCol pairs impact file co-change behavior compared to properly modularized pairs?
- RQ3: How do InSep and InCol pairs evolve over time in software projects?
```

### Target Subject

20 open-source C/C++ and Java projects from GitHub meeting predefined selection criteria (long history, many commits, non-trivial size).

### Constraints

The detection of inappropriate entity modular relationships must be automated and must not rely on developer annotations or ground-truth modular structure.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The dataset is publicly available for replication. Computing co-change and dependency metrics from Git repositories and source code is feasible with standard tools (e.g., pydriller, Understand). No special hardware required; a typical desktop machine should suffice for the 20-project analysis.

## Metadata

```
subfield: Software Maintenance & Evolution
venue: ICSE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```
