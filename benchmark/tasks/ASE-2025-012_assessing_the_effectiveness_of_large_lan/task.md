# Task: ASE-2025-012 — Assessing the Effectiveness of Large Language Models on Multi-Hunk Program Repair

## Background

Automated program repair (APR) has made significant progress, particularly for single-hunk bugs that require edits in one contiguous code region. However, many real-world defects are multi-hunk, requiring coordinated changes across disjoint locations. Most existing APR research and benchmarks focus on single-hunk scenarios, leaving multi-hunk bugs understudied. Recent large language models (LLMs) show promise in code generation, but their ability to repair multi-hunk bugs remains unclear due to inconsistent evaluation setups, ambiguous bug type classification, and aggregated reporting that obfuscates performance on multi-hunk repairs. Moreover, there is no systematic understanding of how the spatial complexity of multi-hunk patches impacts repair difficulty.

## Research Question

How effectively can current large language models repair multi-hunk software bugs, and to what extent does the spatial distribution of the required edits influence their success?

## Experiment Setup

### Datasets
```
- name: Multi-Hunk Bug Dataset
  source: Constructed by filtering open-source Java bug benchmarks (e.g., Defects4J) for patches that modify multiple non-contiguous code locations. The filtering process should exclude single-hunk bugs and keep only patches with at least two hunks. Access: constructable from public Defects4J data (https://github.com/rjust/defects4j) and similar repositories, following guidelines from the original study.
  description: A dataset of 372 real-world multi-hunk bugs from popular Java projects, each consisting of buggy and fixed versions along with a test suite that exposes the defect.
  access: constructable
```

### Baselines
```
- name: GPT-4.1
  reference: OpenAI API, model gpt-4.1 (or equivalent)
- name: O4-MINI
  reference: OpenAI API, model o4-mini (or equivalent)
- name: GEMINI-2.5-FLASH
  reference: Google AI Studio API, gemini-2.5-flash
- name: NOVA-PRO
  reference: Amazon Nova Pro API
- name: MISTRAL-2407
  reference: Mistral AI API, mistral-large-2407
- name: LLAMA3.3
  reference: Meta, available via API or local deployment
```

### Metrics
```
- name: Plausible@1
  definition: The fraction of bugs for which the first generated patch (top-1) parses, compiles, and passes all associated test cases, including the originally failing test.
- name: Total inference cost
  definition: The cumulative monetary cost (in USD) charged by the LLM provider for all API calls made during the repair experiment.
```

### Sub-questions
```
- RQ1: How does the repair success rate vary across different LLMs when applied to multi-hunk bugs?
- RQ2: How do retrieval-based example selection, the granularity of code context (method vs. class vs. file), and feedback from compilation or test failures affect the repair performance of LLMs?
- RQ3: How does the spatial dispersion of buggy hunks (ranging from edits within a single method to edits across multiple files) impact the likelihood of generating a correct patch?
```

### Target Subject

Real-world Java programs containing multi-hunk defects. Examples include bugs from Apache Commons Lang, JFreeChart, and Google Closure Compiler, where patches span non‑contiguous lines across the same or different files.

### Constraints

The evaluation must use only the information available at the buggy version (no oracle from the fix). Each model should be prompted in a zero-shot or few-shot setting with examples from a separate training set, with no fine-tuning. Generated patches are limited to one per bug using deterministic decoding (e.g., temperature = 0) except where the API does not support it. The total inference budget should be tracked, and experiments should be reproducible. The dataset construction must ensure that all selected bugs are truly multi-hunk (≥2 hunks).

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The required multi-hunk bug dataset can be constructed from the Defects4J benchmark, which is publicly available, though careful filtering and patch parsing are needed. All LLMs listed are accessible through commercial APIs, but large-scale evaluation across many bugs and configurations will incur significant costs (several hundred USD). Setting up the evaluation pipeline involves extracting buggy code, crafting prompts, applying patches to the project, and running test suites in a sandboxed environment. Major challenges include handling compilation failures, non-deterministic LLM outputs despite temperature settings, and isolating multi‑hunk bug cases from single‑hunk ones.

## Metadata

```
subfield: LLM for Software Engineering
venue: ASE 2025
year: 2025
difficulty: hard
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```