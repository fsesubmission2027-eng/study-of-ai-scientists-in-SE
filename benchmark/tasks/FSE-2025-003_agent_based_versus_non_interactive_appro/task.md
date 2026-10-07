# Task: FSE-2025-003 — Agent-based versus Non-interactive Approaches for Automated Software Issue Resolution

## Background

Large language models (LLMs) have demonstrated strong capabilities in generating code for isolated problems, but applying them to complex, repository-level software engineering tasks such as bug fixing remains challenging. These tasks require understanding not only the issue description but also cross-file dependencies, existing codebase context, and the ability to make correct changes. The SWE-bench benchmark was introduced to evaluate such end-to-end issue resolution, and recently a variety of autonomous LLM agents have been developed that iteratively use tools, run commands, and incorporate environmental feedback. However, these agent-based systems add substantial complexity, raising the question of whether their interactive, multi-turn design is truly necessary or whether simpler, non-interactive (agentless) approaches can be equally effective. This work aims to rigorously compare these two paradigms on the SWE-bench Lite benchmark to understand the trade-offs in performance, cost, and error localization.

## Research Question

To what extent do complex autonomous LLM agents outperform simpler, non-interactive approaches on software development issue resolution tasks, and what factors contribute to any observed differences?

## Experiment Setup

### Datasets
```
- name: SWE-bench Lite
  source: https://www.swebench.com/lite.html or GitHub: https://github.com/princeton-nlp/SWE-bench
  description: A curated subset of 300 real-world GitHub issues from 12 Python open-source repositories, each consisting of an issue description and the corresponding repository snapshot. The task is to generate a patch that resolves the issue by passing all existing regression tests and a specific reproduction test.
  access: open
```

### Baselines
```
- name: SWE-agent
  reference: Yang et al., 'SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering' (2024)
- name: AutoCodeRover
  reference: Zhang et al., 'AutoCodeRover: Autonomous Program Improvement' (2024)
- name: MarsCode Agent
  reference: Liu et al., 'MarsCode Agent: AI-powered Automated Issue Resolution' (2024)
- name: CodeR
  reference: Chen et al., 'CodeR: Issue Resolving with Multi-Agent Collaboration' (2024)
- name: OpenCSG StarShip
  reference: commercial product (source not available)
- name: Devin
  reference: commercial agent by Cognition AI (source not available)
- name: RAG (retrieval-augmented generation baseline)
  reference: Jimenez et al., 'SWE-bench: Can Language Models Resolve Real-World GitHub Issues?' (2024) – the original BM25-based file retrieval + LLM patch generation baseline
```

### Metrics
```
- name: % Resolved
  definition: Percentage of benchmark issues where the submitted patch passes all regression tests (i.e., tests that were passing before the fix) and the specific reproduction test that validates the issue is fixed.
- name: Avg. $ Cost
  definition: Average monetary cost (in USD) of running the tool on one issue, based on the LLM API pricing for the tokens consumed.
- name: Avg. # Tokens
  definition: Average total number of input and output tokens used in API calls per issue.
- name: % Correct Location (file/function/line)
  definition: Percentage of issues for which the generated patch edits a superset of the edit locations (files, functions, or lines) of the ground-truth developer patch.
```

### Sub-questions
```
- RQ1: How does the issue-resolve rate of agent-based and agentless approaches compare on SWE-bench Lite?
- RQ2: To what extent does the ability to localize the correct edit location correlate with overall fix success?
- RQ3: Which types of issues (e.g., those with explicit reproduction steps) are more or less amenable to agentless methods?
```

### Target Subject

Software development issue resolution on Python repositories. The target systems are open-source Python projects from the SWE-bench Lite collection, such as Django, scikit-learn, seaborn, and others, each containing real-world bug reports or feature requests.

### Constraints

Evaluation must follow the SWE-bench protocol: no access to the ground-truth patch, only the issue description and the repository code snapshot. Agent-based methods may use interactive tools, command execution, and environment feedback during the resolution process. Agentless methods must not rely on multi-turn interaction after the initial patch generation, but may use static analysis, retrieval, or one-shot generation with post-hoc validation. All approaches must output a valid unified diff patch.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The SWE-bench Lite dataset and evaluation harness are publicly available, making replication straightforward. Execution requires an LLM API key (e.g., OpenAI) and may incur significant costs when performing multiple samples per issue (paper reports ~$0.70 per issue for one configuration). The benchmark involves executing patches in Docker containers, so a capable compute environment with internet access is needed. The main challenge lies in implementing a non-interactive but effective agentless approach and in fairly comparing it against a diverse set of agent-based baselines, some of which are closed-source and cannot be directly inspected.

## Metadata

```
subfield: LLM for Software Engineering
venue: FSE 2025
year: 2025
difficulty: medium
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```