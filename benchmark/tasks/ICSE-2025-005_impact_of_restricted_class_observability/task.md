# Task: ICSE-2025-005 — Impact of Restricted Class Observability on Automated Test Generation Effectiveness

## Background

Automated test generation tools often achieve high code coverage but produce tests with limited fault‑finding potential, largely because of inadequate assertions. A major cause is the poor observability of the class under test: private and protected attributes cannot be inspected, and when methods return non‑primitive objects, the generator lacks the ability to check the internal state of those objects. Consequently, many automatically generated tests miss relevant behaviour checks. While prior studies have shown that limited observability thwarts assertion generation in a majority of cases, the extent to which these observability deficits actually impair the fault‑detection capability of generated test suites remains an open empirical question.

## Research Question

To what extent does the observability of the class under test (i.e., visibility of internal state and ability to inspect composed objects) impact the mutation‑based effectiveness of automatically generated tests?

## Experiment Setup

### Datasets
```
- name: SF110 complex‑class subset
  source: SF110 dataset available at https://www.evosuite.org/experimental-data/sf110/; the subset of 100 classes was filtered using a cyclomatic complexity threshold > 3 and is available from the authors of prior studies.
  description: 100 Java classes from the SF110 corpus that are non‑trivial (cyclomatic complexity > 3), representing a diverse set of open‑source projects.
  access: open
```

### Baselines
```
- name: EvoSuite with DynaMOSA algorithm
  reference: EvoSuite (https://www.evosuite.org/); DynaMOSA algorithm as described in Panichella et al., 2018.
```

### Metrics
```
- name: Statement coverage
  definition: Percentage of Java statements exercised by the generated test suite.
- name: Branch coverage
  definition: Percentage of control‑flow branches covered by the test suite.
- name: Overall suite coverage
  definition: Aggregate coverage computed by EvoSuite based on eight target coverage criteria.
- name: Mutation score
  definition: Percentage of artificially seeded mutants (using the default EvoSuite mutation operators) that are detected (killed) by the test suite.
- name: Vargha‑Delaney A12 effect size
  definition: A non‑parametric effect size statistic measuring the probability that a randomly chosen test suite from one treatment outperforms a randomly chosen baseline suite; values above 0.5 indicate a positive effect.
```

### Sub-questions
```
- RQ1: To what extent does the inaccessibility of private/protected class attributes limit mutation score and coverage of automatically generated tests?
- RQ2: To what extent does the inability to generate assertions on non‑primitive return values (composed objects) limit test effectiveness?
- RQ3: How do limited visibility and limited ability to inspect composed objects interact – i.e., does improving one factor alone suffice, or must both be addressed to achieve notable gains?
```

### Target Subject

Non‑trivial Java classes from open‑source projects that encapsulate internal state behind private/protected attributes and/or lack public methods for inspecting the state of returned non‑primitive objects. Examples include classes managing database connections or GUI panel navigation that modify internal state without exposing it through getters that return primitive types.

### Constraints

Test generation must use the same search budget (180 s) and assertion timeout (600 s) as the baseline EvoSuite configuration. Any modifications made to the class under test must not alter the set of coverage goals or the set of mutants used for mutation analysis; all test goals and mutation scoring must be based solely on the original source code.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The SF110 dataset and EvoSuite are publicly available, and the filtered subset of 100 classes can be obtained from prior work or re‑constructed using the cyclomatic complexity threshold. The original study required 6 days of compute on a 20‑core M1 machine to generate 12,000 test suites. The main technical challenge lies in correctly intercepting EvoSuite’s assertion generation without altering the underlying test goals.

## Metadata

```
subfield: Automated Testing & Test Generation
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```