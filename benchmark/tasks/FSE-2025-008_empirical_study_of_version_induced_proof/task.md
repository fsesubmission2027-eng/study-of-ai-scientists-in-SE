# Task: FSE-2025-008 — Empirical Study of Version-Induced Proof Breakages in an Interactive Theorem Prover

## Background

Interactive theorem provers (ITPs) such as Isabelle, Coq, and Lean are essential for developing machine-checked proofs in formal verification. As proof projects grow to hundreds of thousands of lines, maintaining and reusing proofs across different versions of a proof assistant becomes a major challenge. Version updates can break existing proofs due to changes in the logical engine, proof languages, automation heuristics, or library formalizations. These breakages are often hard to diagnose because proof failures provide limited error information and require deep domain knowledge. While several approaches have been proposed to repair proofs after specific types of changes, there is no broad empirical understanding of the spectrum and root causes of version compatibility issues. Such a characterization is necessary to guide the development of robust proof maintenance tools.

## Research Question

What are the common categories, root causes, and resolution patterns of version-induced proof failures in a real-world proof assistant environment?

## Experiment Setup

### Datasets
```
- name: Archive of Formal Proofs (AFP)
  source: https://www.isa-afp.org/
  description: A large repository of formal proofs for Isabelle, containing over 21,000 theory files spanning multiple AFP releases (e.g., AFP-2021, AFP-2022, AFP-2023).
  access: open
- name: Isabelle proof assistant releases
  source: https://isabelle.in.tum.de/
  description: Multiple major versions of the Isabelle proof assistant, e.g., Isabelle2021, Isabelle2022, Isabelle2023, and a development snapshot.
  access: open
```

### Baselines
```
[NOT SPECIFIED IN PAPER]
```

### Metrics
```
- name: Count of compatibility issues
  definition: Number of distinct proof failures (errors, timeouts) encountered when loading and checking a theory file with a given Isabelle version.
- name: Issue type distribution
  definition: Proportion of issues belonging to each predefined category (e.g., theory errors, term errors, proof errors) based on automated classification of error messages.
- name: Root cause categories
  definition: Classification of the underlying change in the proof assistant or library that triggered the failure, derived from analyzing the differences between versions.
- name: Resolution strategy categories
  definition: Classification of the fix or workaround applied in the updated theory to resolve the issue, based on manual inspection of aligned proof files.
```

### Sub-questions
```
- RQ1: What types of compatibility issues occur when upgrading Isabelle and its standard library, and what is their distribution?
- RQ2: What are the root causes of these issues, and how do they relate to changes in the proof assistant or its libraries?
- RQ3: What resolution strategies do proof developers employ to fix version-induced breakages?
```

### Target Subject

A mature interactive theorem prover and its ecosystem of formalized mathematics. Specifically, the study focuses on the Isabelle proof assistant and the Archive of Formal Proofs (AFP), a curated collection of community-developed formal proofs.

### Constraints

Proof checking must be fully automated; only errors reported by the prover's standard checking mechanism are considered (no manual assessment of proof intent). Execution of each proof command must be bounded by a timeout (e.g., 30 seconds) to avoid infinite loops. The study must cover multiple major versions of the prover and a large, representative collection of theories.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All necessary components are publicly available: Isabelle can be downloaded from its official website, and the AFP archive is openly accessible. Executing the full cross-version test matrix requires substantial computational resources (thousands of theory files per pair, each potentially triggering heavy automation), which may take multiple days on a multi-core server. Classifying error types can be automated via parsing structured error messages, but validating root causes and resolution strategies will require manual inspection of a sampled set, which is labor-intensive.

## Metadata

```
subfield: Program Analysis & Verification
venue: FSE 2025
year: 2025
difficulty: hard
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```