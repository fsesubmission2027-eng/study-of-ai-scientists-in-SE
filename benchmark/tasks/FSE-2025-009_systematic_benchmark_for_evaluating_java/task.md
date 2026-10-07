# Task: FSE-2025-009 — Systematic Benchmark for Evaluating Java Deserialization Gadget Chain Detectors

## Background

Insecure deserialization is a top-10 web application vulnerability, and in Java, exploitation often relies on gadget chains—sequences of method invocations that attackers can abuse. Numerous static analysis tools have been proposed to detect these chains, but the evaluation practices are inconsistent: many tools are only tested against a small set of known chains (e.g., from the Ysoserial project) and lack transparent, reproducible comparisons. No standard benchmark systematically covers the diverse code patterns and complexity dimensions that arise in real software, making it difficult to assess the true effectiveness, precision, and recall of these tools. A comprehensive, publicly available benchmark is needed to measure the strengths and weaknesses of gadget chain detectors under controlled conditions.

## Research Question

How can a benchmark be designed to systematically evaluate the precision and recall of Java deserialization gadget chain detection tools across a wide range of code complexities and realistic chain patterns?

## Experiment Setup

### Datasets
```
- name: DeserializationGadgetChainBenchmark
  source: Constructable by the researcher following the described challenge categories and known real‑world chains (e.g., Ysoserial). The dataset consists of multiple small, self‑contained Java programs, each embedding one or more gadget chains with controlled properties.
  description: A set of synthetic test cases covering varying chain depths, inheritance hierarchies, dynamic proxies, entry point types, and other code patterns, together with replicas of publicly known real‑world gadget chains (e.g., from Ysoserial). Ground truth is known by construction.
  access: constructable
```

### Baselines
```
- name: Serianalyzer
  reference: Rasthofer et al., 2019 (original publication)
- name: GadgetInspector
  reference: Baker et al., 2018 (original publication)
- name: SerHybrid
  reference: 2022 (original publication)
- name: Tabby
  reference: 2021 (original publication)
- name: Crystallizer
  reference: 2023 (original publication)
- name: JDD
  reference: 2023 (original publication)
- name: JDeserializer
  reference: 2022 (original publication)
```

### Metrics
```
- name: True Positive Rate (Recall)
  definition: For each test case, the number of true gadget chains correctly reported divided by the total number of actual gadget chains in that case.
- name: False Positive Count
  definition: Number of reported chains that are not actual gadget chains (i.e., false alarms).
- name: Category Coverage
  definition: The number of distinct challenge categories in which a tool achieves perfect precision (zero false positives) and perfect recall (all true chains found).
```

### Sub-questions
```
- RQ1: How does each tool perform (true positives and false positives) across different categories of gadget chain complexity (e.g., varying chain depth, inheritance depth, entry-point types)?
- RQ2: To what extent do the tools' results on the benchmark align with their reported performance on real-world Ysoserial chains?
- RQ3: What precision–recall trade-offs can be observed among the tools when evaluated on a systematic benchmark?
```

### Target Subject

Java deserialization gadget chain detection tools that perform static analysis. Examples of such tools include Serianalyzer, GadgetInspector, SerHybrid, Tabby, Crystallizer, JDD, and JDeserializer.

### Constraints

[NOT SPECIFIED IN PAPER]

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The benchmark must be implemented as a collection of self‑contained Java projects; this requires strong Java and program analysis knowledge. Computational resources are modest: typical static analysis tools run on standard workstations. The primary difficulty lies in designing test cases that comprehensively cover real‑world patterns while guaranteeing the ground truth is unambiguous.

## Metadata

```
subfield: Software Security
venue: FSE 2025
year: 2025
difficulty: medium
paper_type: dataset
award: ACM SIGSOFT Distinguished Paper Award
```