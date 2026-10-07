# Task: ICSE-2025-012 — Ensuring Functional Equivalence When Replacing a Large-Scale Authorization Engine

## Background

Amazon Web Services (AWS) manages access control for over 200 services via a central authorization engine that processes over 1 billion requests per second. Any modification to this engine must guarantee backward compatibility and correctness to avoid disrupting existing customer workflows. Currently, changes undergo rigorous manual review and testing, but these methods cannot provide formal guarantees against subtle behavioral regressions. The challenge is to develop a replacement engine that is guaranteed to be behaviorally equivalent to the legacy system, while also meeting strict performance requirements.

## Research Question

How can a new authorization engine be built to guarantee that it behaves identically to an existing legacy engine for all possible requests, while achieving competitive performance?

## Experiment Setup

### Datasets
```
- name: Production Authorization Request Logs
  source: Restricted; available only with permission from AWS, but similar synthetic datasets can be constructed from public cloud API specifications and access patterns.
  description: A large corpus of real authorization requests from AWS production environments, spanning diverse services and permission configurations. The original study eventually compared against up to 10^15 samples.
  access: restricted
```

### Baselines
```
- name: Original authorization engine (pre-replacement version)
  reference: Internally deployed AWS IAM authorization engine; publicly documented API behavior at https://docs.aws.amazon.com/IAM/
```

### Metrics
```
- name: Behavioral equivalence
  definition: Percentage of test requests for which the new engine produces an identical allow/deny decision to the original engine.
- name: Throughput
  definition: Number of authorization decisions completed per second under sustained load.
- name: Latency
  definition: End-to-end response time measured at the 50th, 95th, and 99th percentiles.
```

### Sub-questions
```
- RQ1: Does the replacement engine produce identical authorization decisions for a large and diverse sample of production requests?
- RQ2: How does the throughput and latency of the replacement engine compare to the original engine under typical and peak loads?
```

### Target Subject

Cloud infrastructure authorization engines that evaluate permissions for API requests. Examples include AWS IAM authorization engine, Google Cloud Identity and Access Management, and Azure RBAC engine.

### Constraints

The replacement engine must run in the existing Java Virtual Machine (JVM) production environment, accept the same request format (e.g., AWS IAM policy evaluation requests), produce identical output decisions for all previously permissible inputs, and integrate without requiring client-side changes.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The production dataset used for differential testing is proprietary and not publicly available; a researcher would need to either gain access or generate a synthetic dataset based on public documentation, which may not capture edge cases. Guaranteeing full behavioral equivalence for all possible requests is extremely challenging and may require substantial formal reasoning effort. The original development effort spanned four years with a team of experts; an AI Scientist must scope the problem (e.g., a simplified authorization model) to make it tractable.

## Metadata

```
subfield: Program Analysis & Verification
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```