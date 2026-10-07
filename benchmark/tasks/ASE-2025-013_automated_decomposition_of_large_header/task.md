# Task: ASE-2025-013 — Automated Decomposition of Large Header Files in C Projects Using Semantic Understanding

## Background

Large header files, often referred to as God Header Files, are included by numerous source files and accumulate many unrelated or loosely related code entities over time, making maintenance and comprehension difficult. Existing automated decomposition approaches group declarations based on syntactic or structural similarity metrics, but they often fail to capture the functional semantics of the code, leading to suboptimal breakdowns and the introduction of cyclic include dependencies that break compilation. Large Language Models (LLMs) have shown promise for semantic code understanding, but in preliminary experiments they struggle with long input files due to token limits and degraded attention, frequently omit important entities (hallucination), and still produce cyclic dependencies. This highlights the need for an approach that can effectively handle large header files while ensuring complete, compilable, and semantically coherent decompositions.

## Research Question

How can large header files be automatically decomposed into compilable, logically cohesive sub-header files that align with developer intent, overcoming input length constraints, entity omission, and cyclic dependency issues?

## Experiment Setup

### Datasets
```
- name: Real-world Header File Decomposition Dataset
  source: Constructable via the described mining process; also available as a companion artifact at a public GitHub repository linked in the original study.
  description: 153 real-world header file decomposition refactorings extracted from the default branches of the top 100 starred C projects on GitHub. Each instance contains the original header file and the developer's ground-truth decomposition into sub-header files. File sizes range from 16 to 3,162 lines (avg. 403), with 4 to 767 code entities per file (avg. 75).
  access: constructable
```

### Baselines
```
- name: Wang et al.'s clustering-based approach
  reference: paper [4] in the study
- name: GPT-4o
  reference: OpenAI GPT-4o model, as used in the preliminary study
- name: DeepSeek-V3
  reference: DeepSeek-V3 model, as used in the preliminary study
```

### Metrics
```
- name: Accuracy (ACC)
  definition: Proportion of code entities assigned to the same cluster in the generated decomposition and the ground truth.
- name: F1-score
  definition: Harmonic mean of precision and recall computed over entity pairs, measuring decomposition similarity to the reference.
- name: MoJoFM
  definition: Move-Join-Fix measure adapted for clustering, quantifying the minimum number of move and join operations to transform the generated decomposition into the reference.
- name: Adjusted Rand Index (ARI)
  definition: Chance-corrected measure of agreement between two clusterings, ranging from -1 to 1.
- name: Normalized Mutual Information (NMI)
  definition: Information-theoretic measure of clustering agreement normalized between 0 and 1.
```

### Sub-questions
```
- RQ1: What is the accuracy (ACC, F1, MoJoFM, ARI, NMI) of state-of-the-art header file decomposition methods, including both traditional metrics-based and LLM-based approaches, when compared to real-world developer refactorings?
- RQ2: How do input file length and the number of code entities affect the completeness (entity coverage) and correctness (absence of hallucinated entities) of LLM-generated decompositions?
- RQ3: What is the frequency and severity of cyclic include dependencies in decompositions produced by different methods, and how does their presence impact compilation success?
```

### Target Subject

Large C header files (God Header Files) that contain a diverse mix of macros, type declarations, variable declarations, and function declarations. Example contexts include core library headers from systems software (e.g., the Git version control system, the OpenSSL cryptographic library, or the Linux kernel).

### Constraints

The decomposition must be based solely on the content of the header file and the broader project's dependency information (include relations and call graphs) obtainable by static analysis. No access to the original developer's refactoring is allowed during inference. The resulting sub-header files must form a valid, compilable program: no circular include relationships, and each entity from the original file must appear exactly once across the generated set of sub-headers.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The dataset can be constructed from public GitHub commits using an adapted version of RefactoringMiner for C, or obtained from the companion artifact repository. Experiments require API access to commercial LLMs (e.g., GPT-4o, DeepSeek-V3) which incurs cost per query; a budget for several thousand API calls should be anticipated. Static analysis (parsing C headers, building dependency graphs) is computationally light and can be performed locally. The main challenge is that off-the-shelf LLMs suffer from input-length constraints and entity hallucination, and any proposed solution must address these without explicit prompting or post-processing hints from this task description.

## Metadata

```
subfield: LLM for Software Engineering
venue: ASE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```