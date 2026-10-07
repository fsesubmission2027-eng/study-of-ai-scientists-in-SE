# Task: ICSE-2025-015 — Empirical Assessment of Color Coding for Goal Model Comprehension in Requirements Engineering

## Background

Requirements engineering (RE) is fundamental to successful software development, enabling stakeholders to identify, document, and manage system specifications. Goal modeling techniques help stakeholders reason about design trade-offs and understand system dependencies, yet these approaches have seen limited practitioner adoption due to the complexity of building and interpreting models. Color coding has been proposed as a visual aid to communicate the satisfaction status of elements within goal models, but there is little empirical evidence validating its effectiveness. A prior controlled experiment suggested that color visualization improved decision-making speed without compromising accuracy, but the findings are limited by a small homogeneous sample and potential confounding factors. This motivates further empirical investigation to strengthen the evidence base and explore whether commonly used color schemes align with users' natural associations.

## Research Question

To what extent does color coding of satisfaction states in goal models affect users' comprehension speed and accuracy, and what color schemes best align with users' intuitive associations for positive and negative outcomes?

## Experiment Setup

### Datasets
```
- name: Goal model experimental stimuli
  source: contact authors of the original controlled experiment or reconstruct from published descriptions
  description: Two goal models of comparable complexity representing different application domains, each containing elements with satisfaction states (satisfied, denied, conflict) that can be rendered with or without color overlays.
  access: constructable
- name: Experimental protocol and instruments
  source: contact authors of the original controlled experiment
  description: Training materials for goal modeling and color visualization, comprehension questionnaires, task completion instruments, and post-study perception surveys used in the original experiment.
  access: restricted
- name: Replication subject response data
  source: collected during replication study; supplementary materials
  description: De-identified participant data including task completion times, answer correctness, color vision test scores, demographic information, color association preferences, and post-study survey responses from approximately 60 participants.
  access: restricted
```

### Baselines
```
- name: Control condition (no color visualization)
  reference: Standard goal model viewing without color-coded satisfaction overlays
- name: Original experiment results
  reference: Published findings from the prior controlled experiment on color visualization in goal models
```

### Metrics
```
- name: Task completion time
  definition: Total time in seconds taken by a participant to answer all comprehension questions about a goal model under a given experimental condition.
- name: Number of correct responses
  definition: Count of correctly answered goal-model comprehension questions out of the total number of questions administered, measuring comprehension accuracy.
- name: Perceived difficulty ratings
  definition: Likert-scale self-reported ratings by participants on the difficulty of understanding the scenario, the model, and answering questions (e.g., 0–10 scale from no difficulty to complete difficulty).
- name: User preference
  definition: Qualitative and quantitative measures of participant preference between color and non-color conditions, collected through post-study surveys.
- name: Color association mapping
  definition: Frequency with which participants associate specific colors (e.g., green, red, blue) with positive outcomes (good, satisfied) versus negative outcomes (bad, denied).
```

### Sub-questions
```
- RQ1: To what extent can users with minimal goal modeling experience learn and apply a color-based visualization to answer comprehension questions about goal models?
- RQ2: How does the presence of color visualization compare to its absence in terms of task completion time and user perceptions of the experience?
- RQ3: How do users rate the overall study experience and the usability of the experimental instruments?
- RQ4: What natural color associations do users hold for positive and negative outcome states, and are commonly used color schemes consistent with these associations?
- RQ5: How do results compare across different study populations and experimental sites, and what factors contribute to variability between studies?
```

### Target Subject

Goal models used in requirements engineering, specifically models with elements that can be in satisfied, denied, or conflicting states. Examples include iStar-based models, GRL (Goal-oriented Requirements Language) models, or Tropos models representing stakeholder requirements and trade-off decisions.

### Constraints

Human subjects must have minimal prior exposure to goal modeling and requirements engineering. Participants must pass a standard color vision screening (e.g., Ishihara test) as an inclusion criterion. The experimental design must use a crossover protocol where each subject experiences both color and control conditions with counterbalancing of condition order and experimental stimuli. The study requires adequate statistical power to detect moderate effect sizes, suggesting a sample size of at least 60 participants. The original experimental materials (goal models, training modules, questionnaires) must be used without modification to enable valid comparison, or any modifications must be documented and justified.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

This is a human subjects study requiring institutional review board (IRB) approval, participant recruitment, and supervised experimental sessions. The experimental materials (goal models, training modules, questionnaires) from the original study must be obtained from the original authors or reconstructed from published descriptions. Statistical analysis requires expertise in mixed-effects modeling and crossover experimental designs. Data collection for 60 or more participants may require several weeks of sessions. The original study's data may be available through supplementary materials or by contacting the authors. Replication fidelity depends on faithfully reproducing the experimental protocol while varying the site and population.

## Metadata

```
subfield: Empirical Study & Human Factors
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```