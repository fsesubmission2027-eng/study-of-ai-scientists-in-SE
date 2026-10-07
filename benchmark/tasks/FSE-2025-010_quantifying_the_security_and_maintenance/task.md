# Task: FSE-2025-010 — Quantifying the Security and Maintenance Trade-offs of Dependency Pinning versus Floating in the npm Ecosystem

## Background

Modern software supply chains rely heavily on open-source components managed through package managers. Projects specify version constraints for their dependencies, typically choosing between floating constraints (allowing automatic minor/patch updates) and pinning (locking to a specific version). Floating enables rapid propagation of security patches but also creates an attack surface for malicious package updates, as seen in recent high-profile incidents. Pinning reduces exposure to such attacks but accumulates outdated dependencies, prolongs vulnerability exposure, and increases dependency conflicts. The security and maintenance costs of these strategies, particularly in large, transitive dependency networks, are poorly understood and have only been studied before the recent shift in awareness of supply chain attacks.

## Research Question

How do dependency pinning and floating strategies affect exposure to malicious package updates, security vulnerabilities, and maintenance burdens across npm dependency graphs, and can coordinated interventions by key packages reduce the ecosystem-wide risk?

## Experiment Setup

### Datasets
```
- name: npm package metadata and dependency graphs (historical)
  source: npm public registry (https://registry.npmjs.org) and Libraries.io (https://libraries.io)
  description: Package version histories, dependency relationships, and download counts for npm packages over multiple time points. Vulnerability data from npm advisories (https://github.com/advisories) or the GitHub Advisory Database. Construction involves resolving dependency graphs from package.json files for a large set of npm packages and GitHub repositories, computing transitive dependencies, and mapping vulnerabilities to specific package versions.
  access: open
```

### Baselines
```
- name: Floating version constraints (no pinning)
  reference: Existing npm behavior using semantic versioning ranges (e.g., ^1.2.0)
- name: Local pinning with no coordination (existing npm pinning)
  reference: npm's package-lock.json mechanism that pins direct dependencies only
- name: Transitive pinning (hypothetical npm extension)
  reference: Proposed mechanism extending package-lock.json to pin transitive dependencies for downstream consumers
- name: Defense selection heuristics (download-based, out-degree-based, betweenness centrality-based, and combinations)
  reference: Analytical baselines for selecting which packages to defend
```

### Metrics
```
- name: Attack surface (number of floating dependencies)
  definition: Total count of floating (non-pinned) direct and transitive dependencies in a project's dependency graph.
- name: Number of outdated dependencies
  definition: Count of dependencies in the resolved graph that are not at their latest available version.
- name: Exposure to security vulnerabilities (n_vuln)
  definition: Number of known vulnerabilities affecting the resolved dependency versions.
- name: Number of breaking changes
  definition: Count of automated updates that would introduce a major version bump or incompatible API change.
- name: Number of dependency conflicts (n_bloated)
  definition: Count of duplicated packages or conflicting version requirements in the resolved dependency graph.
- name: Ecosystem risk (expected download fraction affected)
  definition: Estimate of the average fraction of total npm downloads that would be impacted by a single attack on a package in a set A, computed as (1/|A|) sum_{a in A} (sum of downloads of all packages reachable from a divided by total downloads).
```

### Sub-questions
```
- RQ1: What is the effect of pinning all direct dependencies on the five measures of security and maintenance cost, and how does this effect vary with dependency graph size?
- RQ2: How effective are coordinated pinning strategies (local and transitive) among top-selected upstream packages at reducing the ecosystem-wide risk of malicious package updates?
```

### Target Subject

npm ecosystem (JavaScript packages), including both libraries published to npm and applications hosted on GitHub that depend on npm packages. Examples include widely used libraries such as lodash, express, react.

### Constraints

Dependency graph construction must respect npm's actual resolution algorithm (semantic versioning, package-lock.json semantics). Historical analyses require data from specific time points; simulations assume uniform random attack target selection as a baseline, but sensitivity analyses with alternative attack models (targeting actively maintained projects or fragile packages) are recommended.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All data is available from public npm registries, vulnerability databases, and download count APIs. Processing historical dependency graphs for thousands of packages may require moderate compute resources (CPU-bound, ~GBs of memory) and can likely be executed on a standard server within a few days. The simulation for RQ2 involves computing network centrality measures and evaluating multiple heuristics on a large graph, which is computationally feasible with standard libraries. No special hardware is required.

## Metadata

```
subfield: Software Security
venue: FSE 2025
year: 2025
difficulty: medium
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```