# Task: FSE-2025-001 — Efficient Targeted Unit Test Generation for Runtime Exception Exposure in Java

## Background

Automatic unit test generation is crucial for software quality, but existing tools like Randoop and EvoSuite primarily aim to maximize code coverage for regression testing. They are ineffective for generating targeted tests that trigger specific runtime exceptions at a given program location—a capability needed for tasks such as patch testing, crash reproduction, and static analysis alarm verification. The fundamental challenge is the vast search space of possible unit tests that can reach a target location and produce a specific exception; naive enumeration is infeasible. This motivates the need for a practical system that efficiently synthesizes unit tests to expose runtime exceptions at user-specified locations.

## Research Question

How can a system efficiently generate Java unit tests that trigger a runtime exception at a specific target location in a program, despite the enormous search space of candidate test inputs and method sequences?

## Experiment Setup

### Datasets
```
- name: Java Defect Benchmark Suite (e.g., Defects4J)
  source: https://github.com/rjust/defects4j
  description: A collection of real Java programs with known bugs and exception-triggering locations, commonly used to evaluate test generation and fault localization.
  access: open
- name: Real-world Open-Source Java Projects
  source: GitHub (constructable by selecting Java projects with static analysis alarms)
  description: A set of 51 open-source Java projects used to evaluate the system's ability to inspect null-pointer exception alarms and discover unknown bugs.
  access: constructable
```

### Baselines
```
- name: Randoop
  reference: Pacheco and Ernst, OOPSLA 2007; https://randoop.github.io/randoop/
- name: EvoSuite
  reference: Fraser and Arcuri, ESEC/FSE 2011; https://www.evosuite.org/
```

### Metrics
```
- name: Target Exception Triggering Rate
  definition: Ratio of target exception locations for which a test is generated that triggers the specified runtime exception within the time limit.
- name: Number of Triggered Exceptions
  definition: Total count of distinct runtime exception occurrences triggered across all targets.
- name: Real Bug Discovery
  definition: Number of previously unknown null-pointer exception bugs discovered when applying the system to inspect static analysis alarms in open-source projects.
```

### Sub-questions
```
- RQ1: How does the system perform in terms of triggering exceptions at target locations compared to Randoop and EvoSuite?
- RQ2: How many previously unknown bugs does the system uncover when used to inspect static analysis null-pointer exception alarms in open-source projects?
```

### Target Subject

Java programs that contain potential runtime exceptions such as null pointer exceptions, index out of bounds, and class cast exceptions. Examples: open-source Java libraries and applications from GitHub or the Defects4J benchmark.

### Constraints

The system must work without modifying the source code of the program under test. It must operate within a per-target time budget (e.g., 10 minutes). It should not require manual annotations or test scaffolding beyond providing the classpath of the target program.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

Both Randoop and EvoSuite are publicly available and can be used as baselines. The Defects4J benchmark is open-source and widely used. The additional open-source projects can be selected from GitHub, though collecting and setting up 51 projects requires automation. The computational demands are moderate; experiments can be conducted on a standard multi-core workstation. The main difficulty lies in efficiently exploring the combinatorial search space of method sequences and inputs, a problem that requires non-trivial engineering but is feasible with modern static analysis and test generation tools.

## Metadata

```
subfield: Automated Testing & Test Generation
venue: FSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```