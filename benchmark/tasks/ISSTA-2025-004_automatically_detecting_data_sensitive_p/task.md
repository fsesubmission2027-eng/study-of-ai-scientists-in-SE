# Task: ISSTA-2025-004 — Automatically Detecting Data-Sensitive Performance Anomalies in DBMSs

## Background

Database management systems (DBMSs) use cost-based optimizers to handle varying workloads efficiently, but implementation errors can introduce performance anomalies that appear only under specific data volumes or distributions. Traditional diagnosis relies on developer intuition or comparison with a baseline DBMS, ignoring how data characteristics influence execution. As a result, many data-sensitive performance bugs remain hidden, causing severe slowdowns in production. There is a need for automated, systematic discovery of these elusive anomalies without prior knowledge of the underlying faults.

## Research Question

How can performance anomalies that depend on specific data characteristics be automatically uncovered in database management systems?

## Experiment Setup

### Datasets
```
- name: Synthetic data‑sensitive workload
  source: Constructed by generating SQL DDL and DML statements on‑the‑fly (no fixed URL)
  description: A generator that creates random table schemas, populates them with incremental data, and synthesizes queries sensitive to data size and distribution, simulating evolving workloads.
  access: constructable
```

### Baselines
```
- name: APOLLO
  reference: APOLLO (database performance regression detection tool)
- name: SQLancer CERT
  reference: SQLancer CERT (logic‑bug detection via certificate‑style testing)
- name: Sqirrel
  reference: Sqirrel (SQL fuzzer for DBMS state‑space exploration)
```

### Metrics
```
- name: Number of confirmed performance anomalies
  definition: Count of previously unknown, developer‑confirmed performance bugs that cause significant slowdowns under specific data conditions.
- name: Performance degradation ratio
  definition: Ratio of actual execution time to an estimated expected execution time for a given query and data volume.
- name: Crash bug count
  definition: Number of previously unknown crashes (e.g., segmentation faults, memory errors) triggered during testing.
```

### Sub-questions
```
- RQ1: How many data‑sensitive performance anomalies exist in popular open‑source DBMSs?
- RQ2: How effective are data‑sensitive workloads compared to existing DBMS testing techniques at uncovering such anomalies?
- RQ3: What is the root cause distribution of the discovered anomalies across DBMS components?
```

### Target Subject

A diverse set of widely‑used open‑source relational DBMSs (e.g., MySQL, MariaDB, PostgreSQL, TiDB, Percona, AntDB).

### Constraints

Testing must be fully black‑box, using no manual inspection of source code or pre‑existing known bug databases. Each DBMS should run in an isolated Docker container with 5 CPU cores and 32 GB of main memory, and the entire evaluation per DBMS should complete within two weeks.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All target DBMSs are open‑source and available as Docker images. The dataset is constructed on‑the‑fly, so no external data collection is needed. The computational cost is high: a full evaluation requires up to two weeks per DBMS on a multi‑core server, making large‑scale replication resource‑intensive. The main technical challenge is designing a workload generator that efficiently explores the data space to trigger rare performance cliffs without human guidance.

## Metadata

```
subfield: AIOps & System Reliability
venue: ISSTA 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```