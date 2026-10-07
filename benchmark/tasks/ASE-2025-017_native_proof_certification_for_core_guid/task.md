# Task: ASE-2025-017 — Native Proof Certification for Core-Guided MaxSAT Solvers

## Background

Software engineering tasks such as automated program repair, test minimization, fault localization, and configuration optimization are often cast as Maximum Satisfiability (MaxSAT) problems, where the goal is to satisfy all hard clauses while minimizing the total weight of violated soft clauses. Modern MaxSAT solvers scale to millions of variables and are evaluated in annual competitions, yet unlike SAT solvers—which have long emitted DRAT proofs to certify unsatisfiability—MaxSAT lacks a single, widely supported proof format to guarantee both the feasibility and optimality of its solutions. Existing MaxSAT proof approaches either target only isolated algorithmic phases or reduce solver reasoning to heavy-weighted pseudo-Boolean proofs, leading to impractical verification overhead and ignoring domain-specific optimizations. This absence of efficient certification undermines the trustworthiness of MaxSAT-based tools in safety-critical software engineering contexts. There is a need for a general proof-logging framework that can accompany any modern core-guided MaxSAT solver, scale to competition-size instances, and allow independent verification of optimality with minimal cost.

## Research Question

How can MaxSAT solvers produce automatically verifiable proofs of optimality that are compact, fast to check, and avoid the overhead of translating to general pseudo-Boolean formalisms?

## Experiment Setup

### Datasets
```
- name: 2024 MaxSAT Competition Weighted Exact Track Benchmark Set
  source: MaxSAT Competition 2024 website (accessible via https://maxsat-evaluations.github.io/2024/ or contact competition organizers)
  description: 571 weighted partial MaxSAT instances from diverse application domains, used in the competition's exact track.
  access: open
```

### Baselines
```
- name: certified-cgss (pseudo-Boolean proof generator for VeriPB)
  reference: [NOT SPECIFIED IN PAPER]
```

### Metrics
```
- name: Proof-logging overhead (IR)
  definition: Median percentage change in solver runtime when proof logging is enabled, computed as (logged_time - baseline_time) / baseline_time × 100, reported with 95% bootstrap confidence intervals.
- name: Proof size
  definition: Median size on disk of the emitted proof file, in gigabytes (GB).
- name: Verification time
  definition: Median wall-clock time needed to independently check a proof and confirm the claimed optimal cost, in seconds.
- name: Verification overhead (VO)
  definition: Ratio of verification time to solving time, capturing the relative cost of trust.
- name: Proof size ratio
  definition: Ratio of proof sizes between two proof-generation approaches, used for comparing compactness.
```

### Sub-questions
```
- RQ1: What is the runtime overhead of proof logging during solving, across different logging modes and benchmark characteristics?
- RQ2: How large are the generated proof certificates, and how do they compare to the alternative pseudo-Boolean proof approach?
- RQ3: What is the end-to-end verification cost, and how does it compare to the alternative approach?
```

### Target Subject

Modern core-guided weighted MaxSAT solvers that employ OLL-like algorithms, typical of top-performing entrants in the MaxSAT Competition; examples include solvers that iteratively extract unsatisfiable cores and apply relaxation and hardening steps.

### Constraints

The proof-logging mechanism must not alter the underlying solver's search heuristics or its ability to find optimal solutions. Generated proofs must capture all steps of the OLL algorithm (core extraction, clique detection, hardening, totalizer updates, bound adjustments) and be independently verifiable without access to the solver's internal state. Verification must complete within 2× the solving time and 16 GB memory on competition-grade instances. The framework should be integrable with any OLL-based solver without requiring changes to its core logic.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The benchmark instances are publicly available from the MaxSAT competition website. Verification relies on repeated SAT calls that can be parallelized; standard SAT solvers handle these efficiently on modern workstations with 16 GB RAM. Generating and storing a full DRAT proof for every conflict is not scalable, but black-box SAT calls during verification offer a practical alternative without special hardware. The primary challenge lies in designing inference rules that faithfully capture optimization reasoning while keeping proof sizes compact, but no specialized infrastructure is required.

## Metadata

```
subfield: Program Analysis & Verification
venue: ASE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```