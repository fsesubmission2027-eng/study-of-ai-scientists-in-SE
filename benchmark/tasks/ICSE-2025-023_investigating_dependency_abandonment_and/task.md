# Task: ICSE-2025-023 — Investigating Dependency Abandonment and Developer Reactions in Open-Source Ecosystems

## Background

Open source packages form the backbone of modern software development, yet many are maintained by a small number of volunteers who may disengage, leading to potential abandonment. Dependents worry about security and compatibility risks, but little is known about how often such abandonment occurs or how downstream projects actually respond in practice. This gap hinders informed decision-making for both maintainers and users. A large-scale empirical study is needed to quantify the prevalence of abandonment and characterize removal practices in a real-world ecosystem.

## Research Question

What is the prevalence of abandonment among widely-used packages in an open-source ecosystem, and what factors influence whether and when dependent projects remove an abandoned dependency?

## Experiment Setup

### Datasets
```
- name: npm package metadata and download counts
  source: https://registry.npmjs.org/
  description: Metadata (including release history, version info, download counts) for all npm packages over a six-year observation window.
  access: open
- name: GitHub dependent projects
  source: World of Code (http://worldofcode.org/) or GitHub archive
  description: For each package, a set of GitHub repository snapshots that directly depend on that package at specific points in time, constructed from commit histories.
  access: constructable
- name: OSV vulnerability database
  source: https://osv.dev/
  description: Database of known security vulnerabilities and the package releases that patch them, used to identify security-relevant update events.
  access: open
```

### Baselines
```
- name: Regular package update events
  reference: npm release history (no known vulnerabilities)
- name: Security patch events
  reference: OSV database (first release that patches a publicly known vulnerability)
```

### Metrics
```
- name: Removal rate
  definition: Proportion of exposed dependent projects that remove the abandoned dependency from their manifest files within the observation period.
- name: Time to removal
  definition: Time elapsed (in days) from the abandonment event until the first commit that removes the dependency.
- name: Survival probability
  definition: Kaplan-Meier estimate of the probability that a project has not yet removed the abandoned dependency at a given time t after the event.
```

### Sub-questions
```
- RQ1: How many widely-used packages become abandoned within a six-year observation window?
- RQ2: What percentage of exposed dependent projects react by removing the abandoned dependency, and how quickly do they act?
- RQ3: Which project-level characteristics (e.g., project activity, number of dependencies, presence of an end-of-life notice) are associated with faster or more likely removal?
```

### Target Subject

Widely-used packages (e.g., top 1% by downloads) in the JavaScript npm ecosystem and their direct dependent projects hosted on GitHub.

### Constraints

The study must focus on packages that were widely used during the observation period (e.g., high download counts). Dependent projects are considered active only if they have at least one commit after the abandonment event. For update and security-patch comparisons, projects whose dependency is automatically updated via floating version constraints are excluded. The observation window is six years (e.g., 2014–2020), with reactions tracked until a later cutoff date.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

npm package metadata and download counts are openly available via the registry; dependent project data can be obtained from World of Code or GitHub Archive; vulnerability information is publicly accessible through OSV. Reproducing the full scale requires mining millions of repositories and significant computational resources, but a carefully sampled subset can be processed with moderate hardware. Statistical modelling (survival analysis, logistic regression) requires domain expertise but uses standard libraries.

## Metadata

```
subfield: Software Maintenance & Evolution
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```