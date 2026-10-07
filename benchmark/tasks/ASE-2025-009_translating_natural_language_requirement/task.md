# Task: ASE-2025-009 — Translating Natural Language Requirements to Linear Temporal Logic for Safety-Critical Systems

## Background

The translation of natural language software requirements into formal specifications such as Linear Temporal Logic (LTL) is essential for enabling formal verification in safety-critical industries. Manual translation by domain experts is slow, costly, and error-prone. Existing automation methods are either rule-based, which are inflexible and narrow in scope, or learning-based, which require large labeled datasets and struggle to generalise. Although large language models (LLMs) have shown promise in code generation, directly applying them to NL-to-LTL translation is problematic because industrial requirements contain implicit temporal semantics, deeply nested logical constructs, and cause error compounding due to autoregressive generation. Consequently, there is a need for a robust approach that can reliably produce syntactically valid and semantically correct LTL from realistic, complex natural language requirements.

## Research Question

How can a fully automated system translate natural language software requirements into syntactically valid and semantically correct Linear Temporal Logic specifications, especially for industrial safety-critical systems with complex conditional logic and implicit temporal semantics?

## Experiment Setup

### Datasets
```
- name: Academic NL-to-LTL Benchmark (Circuit, Navigation, Office Email)
  source: Public benchmark from prior work; specific URLs not given in this paper – contact authors of [16], [24]–[26]
  description: Three curated subsets of short, lifted requirements (placeholders for atomic propositions) covering circuit logic, navigation instructions, and office email scenarios.
  access: restricted (via prior authors)
- name: Industrial Aerospace Requirements Dataset
  source: contact authors (proprietary, from industrial partners)
  description: 112 English requirements from a sun-search controller and a propulsion management system for spacecraft, annotated with ground-truth LTL by two experts per requirement and reviewed by a senior engineer. Average sentence length 43.7 tokens, over 60% with ≥2 layers of logical nesting.
  access: restricted
```

### Baselines
```
- name: Direct LLM Prompting (GPT-4o)
  reference: GPT-4o, OpenAI. Few-shot prompting to translate NL to LTL.
- name: NL2SPEC
  reference: Template-guided, staged prompting approach. See prior work referenced in paper for NL2SPEC.
- name: NL2TL
  reference: Prompt-based baseline from Hahn et al., originally for STL, adapted for NL-to-LTL. ICSME 2020 (or relevant reference).
```

### Metrics
```
- name: LTL Syntax Validity
  definition: Percentage of generated formulas that can be successfully parsed by the Spot library into a Büchi automaton.
- name: Exact Match Accuracy
  definition: Semantic and logical equivalence judged independently by two human experts; a match is accepted only when both agree.
- name: Atomic Proposition Recall
  definition: Proportion of atomic propositions in the gold reference that also appear in the generated output.
- name: BLEU Score (abstracted)
  definition: Token‑level BLEU computed after all atomic propositions are replaced by generic placeholders, measuring syntactic structure similarity.
- name: Binary Accuracy (academic only)
  definition: String‑exact match between generated and reference formula without any normalisation or semantic equivalence check.
```

### Sub-questions
```
- RQ1: How does the translation approach perform on standard academic benchmarks compared to existing NL‑to‑LTL methods?
- RQ2: To what extent can the approach accurately translate real‑world industrial requirements with implicit temporal semantics and deep logical nesting?
- RQ3: What types of structural complexities (e.g., nested conditionals, ambiguous temporal expressions) in industrial requirements most hinder translation accuracy, and how can their impact be characterised?
```

### Target Subject

Safety‑critical reactive and embedded systems with natural language requirements, such as spacecraft sun‑search controllers, propulsion management systems, and abstracted logical scenarios (circuit behaviours, navigation instructions, email handling rules).

### Constraints

Evaluation must be fully automated (no manual intervention during translation). Academic benchmarks use lifted placeholders for atomic propositions; industrial dataset contains real domain‑specific vocabulary. Generated LTL formulas must be both syntactically valid (parsable by Spot) and semantically equivalent to the reference. Methods may not use the gold LTL during test.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The academic benchmark is available indirectly from prior authors; the industrial aerospace dataset cannot be publicly shared. Full replication of the industrial evaluation therefore requires access to proprietary requirements or a comparable in‑house dataset. LLM‑based inference (GPT‑4o API) may incur moderate costs. Evaluation on industrial data requires expert human annotators for ground truth and for the Exact Match Accuracy metric. The experimental pipeline can be executed on CPU/GPU with API calls, and a full run may take several hours to a few days depending on API latency.

## Metadata

```
subfield: LLM for Software Engineering
venue: ASE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```