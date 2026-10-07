# Task: ICSE-2025-004 — Enhancing DBMS Differential Testing through Diverse Equivalent Instance Construction

## Background

Database Management Systems (DBMSs) are essential for modern data handling, and ensuring their correctness and reliability is critical. Differential testing is a widely used strategy to establish test oracles by comparing outputs from multiple DBMS instances that execute the same SQL input. Existing schemes include version-based comparison (different versions of the same DBMS) and vendor-based comparison (different DBMS products). Version-based methods may miss bugs due to minor release variations, while vendor-based approaches are hampered by differences in internal features, indexing strategies, and storage mechanisms, making it costly to craft valid, equivalent test inputs. The ideal solution would combine broad implementation diversity with full input compatibility, but current techniques fail to achieve both simultaneously, leaving many bugs undetected.

## Research Question

How can a differential testing framework automatically construct DBMS execution environments that are internally diverse yet accept identical SQL inputs, in order to detect more logic bugs than existing vendor- or version-based approaches?

## Experiment Setup

### Datasets
```
- name: MySQL
  source: https://dev.mysql.com/downloads/mysql/ or https://github.com/mysql/mysql-server
  description: Open-source relational DBMS, version 8.0.x, compiled with AFL++ for coverage feedback.
  access: open
- name: MariaDB
  source: https://mariadb.org/download/ or https://github.com/MariaDB/server
  description: Open-source relational DBMS, forked from MySQL, version 10.x, compiled with AFL++.
  access: open
- name: Percona
  source: https://www.percona.com/downloads/ or https://github.com/percona/percona-server
  description: Open-source enhanced MySQL replacement, version 8.0.x, compiled with AFL++.
  access: open
```

### Baselines
```
- name: SQLancer
  reference: https://github.com/sqlancer/sqlancer or OSDI'20 paper 'Finding Bugs in Database Systems via Query Partitioning'
- name: SQLsmith
  reference: https://github.com/anse1/sqlsmith
- name: SQUIRREL
  reference: https://github.com/s3team/Squirrel or ISSTA'21 paper 'SQUIRREL: Testing Database Management Systems with Language Validity and Coverage Feedback'
```

### Metrics
```
- name: Confirmed Bug Count
  definition: Number of distinct, previously unknown bugs reported to and acknowledged by the DBMS vendors during a fixed testing period (e.g., 24 hours).
- name: Branch Coverage
  definition: Percentage of code branches executed in the DBMS binary as measured by AFL++ edge coverage instrumentation.
- name: Test Case Generation Rate
  definition: Number of valid SQL test cases generated per minute (optional, to measure efficiency).
```

### Sub-questions
```
- RQ1: Can the proposed testing scheme find new bugs in well-tested, production-grade DBMSs?
- RQ2: How does the approach compare in bug-finding capability and code coverage with state-of-the-art DBMS fuzzers?
- RQ3: How does the test generation strategy influence coverage of diverse internal features of the DBMS?
```

### Target Subject

Multiple widely-used relational DBMSs that support multiple storage engines, such as MySQL, MariaDB, and Percona. The tested versions should be recent stable releases compiled with AFL++ for coverage tracking.

### Constraints

All DBMS instances must run in isolated Docker containers with identical resource limits (e.g., 5 CPU cores, 40 GB RAM). The generated SQL test cases must be fully compatible with all compared DBMS instances, requiring no modification between runs. The approach must only rely on publicly documented DBMS features, not on internal implementation specifics. Baseline tools must be configured uniformly and run for the same duration (24 hours). Deduplication of bugs is required to avoid inflated counts.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All three DBMSs and baseline fuzzers are open-source and freely available. Compiling DBMSs with AFL++ is a standard procedure, though it may require significant disk space and up to 1 hour per target. Running a full 24-hour experiment for each tool on each DBMS can take several days of compute, assuming a machine with 32 GB+ RAM and multiple cores. The main challenge lies in designing a novel equivalent-instance construction method that is generic, automated, and yields high diversity without sacrificing SQL compatibility. Potential pitfalls include managing stateful DBMS interactions and avoiding false positives due to permissible output variations.

## Metadata

```
subfield: Automated Testing & Test Generation
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```