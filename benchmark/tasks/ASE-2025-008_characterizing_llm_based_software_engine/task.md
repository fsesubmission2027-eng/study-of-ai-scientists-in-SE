# Task: ASE-2025-008 — Characterizing LLM-based Software Engineering Agent Behaviors through Trajectory Analysis

## Background

Large Language Models (LLMs) are increasingly used to build autonomous agents that automate software engineering tasks such as program repair and issue resolution. These agents generate natural language reasoning, invoke external tools (e.g., compilers, debuggers, test runners), and iteratively refine their solutions. While they show promising results, the internal decision-making processes of such agents remain opaque. Without a systematic understanding of how agents reason, use tools, and respond to feedback, it is difficult to diagnose failures, improve design, or trust their outputs. Currently, there is no established methodology to study the behavioral dynamics of LLM-based software engineering agents at scale, leaving a critical gap in both research and practice.

## Research Question

What are the behavioral characteristics of LLM-based software engineering agents during automated program repair, and how do they differ between successful and unsuccessful task completions?

## Experiment Setup

### Datasets
```
- name: Agent Trajectory Dataset
  source: Replication package of the original study (GitHub URL to be provided upon acceptance).
  description: A collection of 120 thought-action-result trajectories from three state-of-the-art LLM-based agents executing real-world program repair tasks. Each trajectory captures iterative steps consisting of a natural language thought, an external action (e.g., search, run tests, generate fix), and the tool’s result.
  access: open
```

### Baselines
```
[NOT SPECIFIED IN PAPER]
```

### Metrics
```
- name: Iteration count
  definition: Number of thought-action-result triples per trajectory.
- name: Token consumption (input and output)
  definition: Total number of tokens consumed by the LLM for input prompts and generated outputs across a full trajectory.
- name: Action category distribution
  definition: Relative frequency of each action type (e.g., search, generate fix, run tests) based on a manually defined categorization scheme.
- name: Frequent action sequences
  definition: Recurring sub-sequences of actions (e.g., n-grams) mined from all trajectories, separately for successful and failed runs.
- name: Thought-action-result coherence
  definition: Semantic alignment between the expressed reasoning, the chosen action, and the observed result, rated by human annotators using predefined relationship categories.
```

### Sub-questions
```
- RQ1: What are the overall properties of trajectories, such as the number of iterations and consumed LLM tokens?
- RQ2: What kinds of actions do agents perform, and what sequential patterns emerge within trajectories?
- RQ3: How do agents develop and adjust their reasoning and actions throughout task execution, and how coherent are thoughts, actions, and feedback?
```

### Target Subject

LLM-based autonomous software engineering agents designed for automated program repair. These agents iteratively reason, invoke tools (e.g., compilers, test runners, search APIs), and modify source code to fix bugs. Examples include RepairAgent, AutoCodeRover, and OpenHands.

### Constraints

Analysis must rely solely on the provided trajectory logs; no modifications to the agents' internal logic or execution environment are permitted. Manual annotation of coherence must be performed by annotators with software engineering knowledge, without access to task ground truth during labeling to avoid outcome bias.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The trajectory dataset is available from the original study's replication package (publicly accessible after publication). The analysis involves lightweight statistical computations, sequence mining, and visualization, which can be performed on a standard CPU. The main resource bottleneck is the manual annotation of coherence for 120 trajectories, requiring trained human annotators. No large GPU resources are needed.

## Metadata

```
subfield: LLM for Software Engineering
venue: ASE 2025
year: 2025
difficulty: medium
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```