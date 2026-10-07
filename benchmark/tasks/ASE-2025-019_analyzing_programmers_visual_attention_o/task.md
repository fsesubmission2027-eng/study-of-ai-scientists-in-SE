# Task: ASE-2025-019 — Analyzing Programmers' Visual Attention on Call Graphs During Code Summarization

## Background

Code summarization is a critical task for software maintenance, requiring developers to comprehend code in its project context. While eye-tracking studies have shed light on how programmers understand isolated code units, there is little understanding of how they gather contextual information from the project structure, particularly the function call graph. Prior research has used call graphs to represent dependencies between methods, but no metrics exist to quantify how programmers visually explore these graphs when summarizing a method. This limits our ability to assess the effectiveness of different comprehension strategies at the project level and to guide automated summarization tools.

## Research Question

How do programmers' visual attention patterns on the function call graph relate to the quality of their method summaries and their confidence in those summaries?

## Experiment Setup

### Datasets
```
- name: Original eye-tracking study (Study 1)
  source: Available upon request from the original study authors (see prior publication)
  description: Eye-tracking data from 10 programmers summarizing methods in five Java projects, including fixation data, call graphs, summary texts, quality ratings (sum of accuracy, conciseness, completeness, clarity), and confidence scores (1-5).
  access: restricted
- name: Replication eye-tracking study (Study 2)
  source: Available upon request from the study organizers
  description: A new dataset collected with the same procedure, comprising 12 additional programmers (total ~45 hours of time-on-task data) with the same annotation schema for summaries and confidence.
  access: restricted
```

### Baselines
```
[NOT SPECIFIED IN PAPER]
```

### Metrics
```
- name: Summary quality score
  definition: Total score out of 20, computed as the sum of human ratings on accuracy, conciseness, completeness, and clarity for a generated summary.
- name: Confidence rating
  definition: Self-assessed confidence on a 1–5 Likert scale provided by the programmer immediately after summarizing.
- name: Call graph method coverage
  definition: Count of distinct methods (nodes) in the target method's call graph that the programmer fixates on during the summarization task.
- name: Call graph depth coverage
  definition: Maximum depth (number of call edges from the target method) reached in the call graph by the programmer's fixations.
```

### Sub-questions
```
- RQ1: How do programmers visually interact with a method's call graph during summarization?
- RQ2: How do different call graph traversal strategies relate to the quality of the written summaries?
- RQ3: How do these strategies relate to the programmers' confidence in their summaries?
```

### Target Subject

Programmers summarizing non-trivial methods in open-source Java projects while their eye movements are tracked. Example projects include an image manipulation library, a machine learning toolkit, a desktop audiobook application, a statistical NLP package, and a strategy game. The methods are selected to exclude simple getters/setters and require some domain functionality.

### Constraints

Analysis must use the provided eye-tracking datasets where only methods with at least one caller or callee are considered. Call graphs are truncated to depth 5. Methods with no fixations due to technical recording issues are excluded.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

Both datasets (total 22 participants, 88 hours of raw eye-tracking data) can be obtained from the study organizers. Processing requires the iTrace eye-tracking suite for fixation extraction and IntelliJ for call graph generation. The analysis is primarily statistical (correlation, regression) and does not require GPU resources. The main challenge is the careful alignment of gaze coordinates with source code methods, which is handled by existing tools.

## Metadata

```
subfield: Empirical Study & Human Factors
venue: ASE 2025
year: 2025
difficulty: medium
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```