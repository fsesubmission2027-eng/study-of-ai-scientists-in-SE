# Task: ASE-2025-014 — Cross-System Log Anomaly Detection Without Log Parsing

## Background

Modern large-scale software systems generate massive volumes of logs that are critical for anomaly detection and system reliability. Manual inspection is infeasible, prompting the development of automated log anomaly detection methods. However, supervised techniques require expensive labeled data, and most unsupervised or semi-supervised approaches depend on log parsing to extract templates, assuming stable log formats. In practice, software version upgrades and architectural changes cause log evolution, breaking parsing-based pipelines and reducing anomaly detection accuracy. Furthermore, transferring learned models from one system (e.g., a mature supercomputer) to another (e.g., a new data processing cluster) remains a significant challenge, as existing cross-system methods often assume structural similarities that do not hold across heterogeneous environments. This task targets the design of a robust anomaly detection framework that can operate without parsing and generalize to unseen target systems using only labeled logs from source systems.

## Research Question

How can we detect anomalies in system logs across heterogeneous, previously unseen target systems without requiring log parsing or labeled anomaly data from those systems?

## Experiment Setup

### Datasets
```
- name: Liberty
  source: https://github.com/logpai/loghub
  description: Supercomputing log dataset from the Liberty system, containing normal and anomaly logs.
  access: open
- name: Thunderbird (TDB)
  source: https://github.com/logpai/loghub
  description: Supercomputing log dataset from the Thunderbird system.
  access: open
- name: Spirit
  source: https://github.com/logpai/loghub
  description: Supercomputing log dataset from the Spirit system.
  access: open
- name: BGL
  source: https://github.com/logpai/loghub
  description: Supercomputing log dataset from the BlueGene/L system.
  access: open
- name: Hadoop2
  source: https://github.com/EvLog/dataset
  description: Versioned log dataset from Hadoop distributed processing system (version 2).
  access: open
- name: Hadoop3
  source: https://github.com/EvLog/dataset
  description: Versioned log dataset from Hadoop distributed processing system (version 3).
  access: open
- name: Spark2
  source: https://github.com/EvLog/dataset
  description: Versioned log dataset from Spark distributed processing system (version 2).
  access: open
- name: Spark3
  source: https://github.com/EvLog/dataset
  description: Versioned log dataset from Spark distributed processing system (version 3).
  access: open
```

### Baselines
```
- name: LogRobust
  reference: LogRobust: Robust Log-based Anomaly Detection on Unstable Log Data (ESEC/FSE 2019)
- name: PLELog
  reference: PLELog: Semi-supervised Log-based Anomaly Detection via Probabilistic Label Estimation (ICSE 2021)
- name: EvLog
  reference: EvLog: A Multi-Level Representation Learning Framework for Log Anomaly Detection under Software Evolution (ICSE 2022)
- name: LogTransfer
  reference: LogTransfer: Transfer Learning for Log-based Anomaly Detection (IEEE TSC 2019)
- name: LogTAD
  reference: LogTAD: Adversarial Domain Adaptation for Log-based Anomaly Detection (ICSE 2020)
- name: MetaLog
  reference: MetaLog: Meta-Learning for Log-based Anomaly Detection with Limited Supervision (ASE 2023)
```

### Metrics
```
- name: Precision
  definition: Proportion of detected anomalies that are true anomalies.
- name: Recall
  definition: Proportion of true anomalies that are correctly detected.
- name: F1-score
  definition: Harmonic mean of precision and recall, treating anomaly detection as a binary classification task.
```

### Sub-questions
```
- RQ1: How well does the method perform when training and testing on different partitions of the same system (single-system generalization)?
- RQ2: How well does the method transfer between different systems of the same type (homogeneous-system generalization)?
- RQ3: How well does the method transfer across systems of entirely different types (heterogeneous-system generalization)?
```

### Target Subject

Log files from large-scale computing systems, specifically supercomputing clusters (e.g., Liberty, Thunderbird) and distributed data processing systems (e.g., Hadoop, Spark), which produce large volumes of semi-structured text logs with evolving formats across software versions and system architectures.

### Constraints

No log parsing or template extraction may be used; raw log messages are the only input. No labeled anomaly samples from the target system are permitted during training; the method must generalize in a zero-shot manner using only source system data. The approach must handle completely unseen log formats and distribution shifts across systems.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All datasets are publicly available from established repositories (Loghub for supercomputer logs, and the EvLog dataset for Hadoop/Spark versioned logs). Baselines have open-source implementations or can be reimplemented. Training BERT-based models on multiple datasets requires moderate GPU resources; full experimental evaluation over multiple source-target combinations may need several days of compute time. The primary challenge is managing the combinatorial setup and ensuring fair comparison across diverse systems.

## Metadata

```
subfield: AIOps & System Reliability
venue: ASE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```