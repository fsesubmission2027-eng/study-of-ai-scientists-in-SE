# Task: ISSTA-2025-005 — Algorithmic Alignment of Graph Neural Networks for Emulating Data-Flow Analysis

## Background

Data-flow analysis (DFA) is a fundamental program analysis technique used in compilers and vulnerability detection. It iteratively propagates facts through a control-flow graph using meet and transfer functions. Graph Neural Networks (GNNs) follow a similar message-passing paradigm, making them a natural candidate for learning DFA-like reasoning. However, typical GNNs do not align well with DFA: DFA uses bit-vectors with independent bitwise updates (noninterference), while GNNs use dense vectors where each element depends on the full neighbor representation; also, DFA's input arguments are consumed at specific stages, unlike standard GNNs that mix all information at the initial node embedding. Bridging these gaps is crucial to achieve high generalization, especially when training on small programs and testing on much larger ones.

## Research Question

To what extent can Graph Neural Networks be designed to align with data-flow analysis algorithms, and how does such alignment affect generalization performance, trajectory length extrapolation, and sample efficiency?

## Experiment Setup

### Datasets
```
- name: POJ-104/0/50 training set
  source: Publicly available: POJ-104 dataset from https://sites.google.com/site/treebasedcnn/ (programs filtered to 0–50 CFG nodes)
  description: C programs from an online judge, with control-flow graphs and bit-vector ground-truth states for a reaching-definitions analysis. Training subset contains programs with up to 50 nodes each.
  access: constructable
- name: POJ-104/500/600 test set
  source: Same source, programs with 500–600 CFG nodes
  description: Medium-large programs (500–600 nodes) for evaluating generalization to larger graph sizes.
  access: constructable
- name: POJ-104/600/700 test set
  source: Same source, programs with 600–700 CFG nodes
  description: Large programs for generalization testing.
  access: constructable
- name: POJ-104/900/1000 test set
  source: Same source, programs with 900–1000 CFG nodes
  description: Very large programs for extreme generalization evaluation.
  access: constructable
- name: Truncated training sets (10, 5, 1 step)
  source: Derived from POJ-104/0/50 by keeping only the last n steps of the execution trace
  description: Training sets where each sample's trajectory is truncated to 10, 5, or 1 final steps, used to assess learning from short demonstrations.
  access: constructable
```

### Baselines
```
- name: Standard GNN (no DFA-specific alignment)
  reference: Based on typical message-passing architectures (e.g., Graph Attention Networks, Veličković et al., ICLR 2018). No per-state independence or staged input injection.
- name: GNN with per-state independent computation (noninterference only)
  reference: Implements row-wise independent state updates to mimic DFA's bit-vector noninterference property, but does not account for stage-specific input injection.
```

### Metrics
```
- name: Last-step precision
  definition: Fraction of correctly predicted bits among all bits predicted as 1 in the final data-flow state.
- name: Last-step recall
  definition: Fraction of true bits that are correctly predicted in the final state.
- name: Last-step F1 score
  definition: Harmonic mean of last-step precision and recall.
- name: Mean step F1 score
  definition: Average F1 score computed over all intermediate prediction steps of the execution trace.
```

### Sub-questions
```
- RQ1: How does training with vs. without trajectory supervision (intermediate state labels) affect GNNs’ ability to generalize to larger programs?
- RQ2: Can GNNs trained on truncated trajectories (fewer propagation steps) successfully predict full-length traces on much larger test programs?
- RQ3: What is the sample efficiency of different GNN designs when only a small number of training programs are available?
```

### Target Subject

C programs from an online judge platform, with varying sizes (10–1000 control-flow graph nodes) and a classic reaching-definitions data-flow analysis. Examples include simple algorithmic programs like sorting, tree traversals, and numerical computations.

### Constraints

Training is restricted to programs with at most 50 CFG nodes; testing is performed on programs with up to 1000 nodes. In sample-efficiency experiments, only a fraction (e.g., 50) of the training samples may be used. The ground-truth DFA states are computed via standard iterative algorithm and must not be employed during inference.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The POJ-104 dataset is publicly available; ground-truth data-flow facts can be precomputed with a classical static analysis tool (e.g., a simple reaching-definitions pass). GNN training requires moderate GPU resources (a single modern GPU is sufficient). The main technical challenge lies in correctly implementing the GNN models that enforce per-state independence and stage-specific input usage, which may demand careful engineering and hyperparameter tuning. Dataset construction and preprocessing are straightforward.

## Metadata

```
subfield: Program Analysis & Verification
venue: ISSTA 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```