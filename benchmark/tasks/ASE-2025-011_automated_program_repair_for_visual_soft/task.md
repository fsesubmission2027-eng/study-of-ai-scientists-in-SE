# Task: ASE-2025-011 — Automated Program Repair for Visual Software Issues from Multimodal Issue Reports

## Background

Automated program repair (APR) techniques aim to reduce manual effort by automatically fixing software defects. With the rise of large language models (LLMs), LLM-driven APR systems have shown promise, but existing benchmarks evaluate them only on unimodal (text-only) issue reports. However, many real-world software issues involve graphical user interfaces, and bug reports often include both textual descriptions and screenshots that provide crucial visual context. Despite their importance, most LLM-based APR systems fail to leverage visual information, and recent benchmarks like SWE-bench M reveal a dramatic performance drop when systems trained on text-only data face multimodal bugs. This gap underscores the urgent need for repair systems capable of jointly understanding textual and visual issue reports.

## Research Question

How can an automated program repair system effectively utilize both textual issue descriptions and attached screenshots to localize and fix bugs in graphical user-facing software?

## Experiment Setup

### Datasets
```
- name: SWE-bench M
  source: GitHub: https://github.com/SWE-bench/SWE-bench-M (or official leaderboard repository)
  description: A multimodal benchmark containing 619 real-world GitHub issue instances from 17 JavaScript libraries that involve visual outputs; each instance provides an issue description, codebase snapshot, and relevant screenshots.
  access: open
```

### Baselines
```
- name: SWE-agent
  reference: Yang et al., 2024, SWE-agent: Agent-Computer Interfaces for Autonomous Software Engineering
- name: SWE-agent Multimodal
  reference: Extension of SWE-agent for multimodal inputs (from SWE-bench M paper)
- name: SWE-agent JavaScript
  reference: SWE-agent adapted for JavaScript (from SWE-bench M paper)
- name: Agentless
  reference: Xia et al., 2024, Agentless: Demystifying LLM-based Software Engineering Agents
- name: Agentless Lite
  reference: Open-source lightweight variant of Agentless (available on GitHub)
- name: RAG
  reference: Retrieval-augmented generation baseline, as described in SWE-bench M paper
- name: Globant Code Fixer Agent
  reference: Closed-source commercial system on SWE-bench M leaderboard
- name: Zencoder
  reference: Commercial repair system on SWE-bench M leaderboard
- name: Computer-Use Agents
  reference: Claude Computer Use (Anthropic) and similar agents that operate GUI environments
```

### Metrics
```
- name: Resolved instances
  definition: The number of unique task instances for which the generated patch correctly resolves the reported issue, as determined by the benchmark's automated validation infrastructure.
```

### Sub-questions
```
- RQ1: How does a repair system that processes visual information perform compared to existing text-based repair systems on multimodal bug reports?
- RQ2: To what extent does incorporating visual context from screenshots improve fault localization?
- RQ3: How effectively can visual outputs be used to validate patches in the absence of test cases?
```

### Target Subject

JavaScript libraries for building visual, user-facing software, such as data visualization (e.g., D3.js), diagramming (e.g., Mermaid), and interactive mapping (e.g., Leaflet).

### Constraints

The system must not depend on pre-existing test suites or reproduction scripts; only the provided issue text, screenshots, and codebase are available. Evaluation follows SWE-bench M protocols where patches are verified by whether they resolve the issue, without executing traditional test cases.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The SWE-bench M dataset is publicly accessible. Implementation requires access to LLM APIs (e.g., GPT-4), which incurs financial cost. The system will need to process screenshots, reason about code, and possibly execute JavaScript to capture visual outputs, adding technical complexity. Reproducing the full evaluation across 517 test instances demands robust automation and integration with the benchmark's harness.

## Metadata

```
subfield: LLM for Software Engineering
venue: ASE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```