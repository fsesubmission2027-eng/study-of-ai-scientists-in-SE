# Task: ISSTA-2025-008 — Automated Test Scenario Generation for Multi-Vessel COLREGS Compliance in Autonomous Surface Vehicles

## Background

Autonomous surface vehicles (ASVs) must obey the International Regulations for Preventing Collisions at Sea (COLREGS) to operate safely, but these rules are intentionally underspecified and become ambiguous in multi-vessel encounters. Current testing relies on manually designed scenarios or historical AIS data, which do not scale to complex multi-ship situations or cover rare ambiguous cases. The maritime domain differs fundamentally from road traffic: vessel dynamics are more complex, geometry is unconstrained, actor sizes vary by orders of magnitude, and trajectories are shaped by rules rather than roads, making automotive test generation techniques unsuitable. An ideal test scenario generator must satisfy five key properties: relevance (hazardous, ambiguous situations), diversity (semantically distinct tests), completeness (full coverage of possible encounters), scalability to many vessels, and speed. Existing synthetic generation approaches adapted from automotive testing struggle to provide sufficient diversity and completeness as the number of vessels grows, while real-world AIS data lacks relevance for multi-vessel scenarios. This motivates the need for new techniques that can systematically produce test suites meeting all five desiderata.

## Research Question

How can a synthetic test scenario generator automatically create multi-vessel COLREGS encounter scenarios that are simultaneously relevant, diverse, complete, scalable, and fast, enabling systematic safety assurance of autonomous surface vessels?

## Experiment Setup

### Datasets
```
- name: CommonOcean benchmark
  source: GitHub (refer to the CommonOcean project for AIS-based encounter data)
  description: Real-world maritime encounter scenarios extracted from Automatic Identification System (AIS) data, predominantly featuring two-vessel interactions.
  access: open
- name: COLREGS functional equivalence classes
  source: [NOT SPECIFIED IN PAPER]
  description: The exhaustive set of semantically distinct, logically consistent multi-vessel encounter scenarios derived from a formal model of COLREGS rules (based on functional abstraction and graph-shape equivalence). Can be constructed programmatically for a given number of vessels and parameter ranges.
  access: constructable
```

### Baselines
```
- name: Search-based maritime scenario generation
  reference: Generic adaptation of automotive search-based scene generation: an optimization method that searches initial vessel placements to maximize a COLREGS relevance score.
- name: Rejection-sampling maritime scenario generation
  reference: Generic adaptation of automotive sampling-based scene generation: random drawing of vessel states filtered by COLREGS encounter criteria.
- name: CommonOcean real-world AIS scenarios
  reference: Pre-collected encounter scenarios from the CommonOcean benchmark.
```

### Metrics
```
- name: Relevance ratio (T ∩ C)
  definition: Fraction of generated scenarios that are both relevant (vessels are on a COLREGS-defined collision course) and consistent (logically admissible under the formal COLREGS model).
- name: Ambiguous relevance ratio (A ∩ C)
  definition: Among consistent scenarios, the fraction that are ambiguous (more than one interpretation of COLREGS duties exists for at least one vessel).
- name: Equivalence class coverage
  definition: Percentage of all distinct relevant and consistent functional equivalence classes (grouped by abstract encounter shape) that are represented by at least one generated scenario.
- name: Distribution divergence
  definition: A statistical measure (e.g., Kullback-Leibler divergence) quantifying how the empirical distribution of generated scenarios across equivalence classes deviates from a uniform distribution.
- name: Average generation time
  definition: Mean wall-clock time required to produce one valid scenario, averaged over multiple runs for a fixed problem size.
```

### Sub-questions
```
- RQ1: How relevant are the generated test scenarios compared to those produced by search-based, rejection-sampling, and AIS-derived baselines?
- RQ2: How diverse and complete is the test suite in terms of covering all semantically distinct relevant encounter classes, and how uniform is the coverage distribution?
- RQ3: How does generation time scale with the number of vessels, and how does it compare to existing synthetic approaches?
```

### Target Subject

Autonomous surface vessel collision-avoidance control software required to comply with COLREGS. The system under test is the 'own-ship' controller; scenarios provide initial positions, headings, and speeds of the own-ship and target vessels. Example controllers include open-source marine autopilots (e.g., ArduPilot/Rover, MOOS-IvP) or academic COLREGS-compliance algorithms.

### Constraints

Scenario generation must operate at the functional (logical) level without requiring high-fidelity hydrodynamic simulation. Generated scenarios must be processable by a COLREGS rule checker based on the formal model that defines relevance, consistency, and ambiguity. The generator must not rely on pre-existing multi-vessel AIS data. Scalability should be demonstrated up to at least 6 vessels. The evaluation uses the same functional abstraction and vessel parameter ranges as in the reference formal model.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The CommonOcean AIS dataset is publicly available. The COLREGS formal model and associated equivalence classes can be implemented from published international regulations and the cited abstraction rules. The baselines (search-based optimization and rejection sampling) are standard and easy to replicate. Evaluation does not require high-fidelity simulators; experiments can run on a modern multi-core CPU with 32 GB RAM and take a few hours of computation. The most technically demanding part is correctly implementing the shape-based equivalence class logic to compute coverage metrics.

## Metadata

```
subfield: AI/ML System Testing
venue: ISSTA 2025
year: 2025
difficulty: medium
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```