# Task: ASE-2025-016 — Reducing Redundant Monitor Creation and Event Signaling in Runtime Verification for Testing

## Background

Runtime verification (RV) checks running programs against formal specifications and has been shown to uncover hundreds of additional bugs when applied to passing test suites. Despite its promise, high runtime overhead—often exceeding 5,000× slowdown—prevents adoption in continuous integration workflows. Recent empirical studies have revealed that during testing, over 99% of monitor instances created for parametric specifications and more than 99.99% of events signaled for non-parametric specifications are redundant, meaning they repeat checks already performed by other monitors. Existing overhead reduction techniques either target production settings or rely on static analyses with limited applicability to test-time monitoring. Consequently, there is an unmet need for a practical, on-the-fly mechanism to eliminate redundant monitoring during testing while preserving the ability to detect specification violations.

## Research Question

To what extent can runtime verification overhead during testing be reduced by selectively skipping the creation of redundant monitors and the signaling of redundant events without significantly compromising violation detection?

## Experiment Setup

### Datasets
```
- name: Single-revision benchmark
  source: https://github.com/SoftEngResearch/Valg (list of artifact project revisions)
  description: 64 open-source Java projects, each at a single revision, used to evaluate monitoring performance.
  access: open
- name: Multi-revision benchmark
  source: https://github.com/SoftEngResearch/Valg
  description: 46 open-source Java projects with multiple consecutive revisions, used to study parameter transfer across versions.
  access: open
```

### Baselines
```
- name: JavaMOP
  reference: F. Chen, G. Roşu. JavaMOP: A monitoring-oriented programming environment for Java. TACAS 2005.
- name: TraceMOP
  reference: H. Guan, O. Legunsen. TraceMOP: Tractable and Practical Explicit-Monitor Runtime Verification. OOPSLA 2021.
```

### Metrics
```
- name: Speedup
  definition: The ratio of the total monitoring time of the baseline tool to that of the selective approach.
- name: Violation Preservation
  definition: The percentage of specification violations detected by the baseline tools that are also detected by the selective approach.
- name: Unique Trace Coverage
  definition: The percentage of distinct event sequences (traces) checked by the baseline tools that are also checked by the selective approach.
- name: Redundancy Reduction
  definition: The percentage of redundant monitor creations or event occurrences avoided, computed as (baseline redundant events − selective redundant events) ÷ baseline redundant events × 100.
```

### Sub-questions
```
- RQ1: How much faster does selective monitoring make runtime verification compared to full monitoring, and to what extent does it preserve the detection of specification violations?
- RQ2: What fraction of unique traces is retained, and how does selective monitoring reduce redundant monitors and events?
- RQ3: How does hyperparameter tuning affect the trade-off between speed and unique trace coverage, and can tuned parameters remain effective when software evolves across revisions?
```

### Target Subject

Open-source Java projects from diverse application domains, such as utility libraries, parsers, and web frameworks. Examples include projects that involve parsing expressions, generating random data, or multi-threaded operations (e.g., Apache Commons components, asterisk.java, expression.parser).

### Constraints

The approach must operate on-the-fly, using only information from past execution traces; it must not rely on access to future program paths. It should be compatible with the JavaMOP monitoring framework and work for both parametric and non-parametric specifications. No specific time or memory budget is prescribed.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All datasets and baseline tools (JavaMOP, TraceMOP) are publicly available in accompanying repositories. Implementing and evaluating a selective monitoring technique requires modifications to these tools and running experiments across a large set of projects, which may take several CPU-hours but does not require GPU resources. The main technical challenge is designing an online decision strategy that accurately identifies redundant items while operating within the instrumentation framework.

## Metadata

```
subfield: Program Analysis & Verification
venue: ASE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```