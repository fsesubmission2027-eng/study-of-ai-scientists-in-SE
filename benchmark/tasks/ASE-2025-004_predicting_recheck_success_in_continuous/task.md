# Task: ASE-2025-004 — Predicting Recheck Success in Continuous Integration

## Background

Continuous Integration (CI) systems automatically run tests on code changes, but flaky test failures cause false alarms. Developers often issue "recheck" commands to rerun tests, but many rechecks fail again, wasting developer time and compute resources. Prior work has quantified this waste, but little is known about what factors distinguish rechecks that ultimately succeed from those that fail. Understanding these factors could help developers make informed decisions about when to recheck and avoid wasted effort.

## Research Question

To what extent can we predict whether a CI recheck request will ultimately succeed, and which features of the build, bot, job, and user history are most indicative of a successful outcome?

## Experiment Setup

### Datasets
```
- name: OpenStack Recheck Dataset
  source: Constructed from the OpenStack Gerrit API; processed data and feature extraction code are available in a replication package (contact study authors for exact link)
  description: 314,947 recheck requests extracted from 2,285 OpenStack projects over a 10-year period, with associated features such as bot success ratio, job success ratio, patch size, file success ratio, user history, and timestamp details.
  access: open (requires construction from public Gerrit data or use of provided processed data)
```

### Baselines
```
- name: Random Guessing
  reference: Baseline that predicts recheck success with the overall success rate of rechecks in the training set (i.e., random with probability equal to success rate).
```

### Metrics
```
- name: AUROC
  definition: Area under the receiver operating characteristic curve; measures the probability that a randomly chosen successful recheck is ranked higher than a failed one.
- name: Brier Score
  definition: Mean squared difference between predicted probability and actual outcome (0 for fail, 1 for success); lower values indicate better calibration.
- name: AUPRC
  definition: Area under the precision-recall curve; evaluates prediction performance when the positive class (success) is rare.
- name: Optimism
  definition: Difference between apparent performance on training data and performance on bootstrap-corrected test data; measures overfitting.
```

### Sub-questions
```
- RQ1: How accurately can the model discriminate between successful and failed rechecks, and how well-calibrated are its predictions?
- RQ2: What categories of features (bot history, job history, patch characteristics, user history, timing) contribute most to predicting recheck outcomes, and how sensitive are these features to the time window?
```

### Target Subject

CI recheck requests in large-scale, multi-project code review systems with bot-driven testing (e.g., Gerrit with Zuul/Jenkins). For example, the OpenStack ecosystem, or any project using similar infrastructure that supports 'recheck' commands.

### Constraints

The prediction must rely solely on historical data available at the time of the recheck request (bot success rates, job success rates, patch metadata, user activity, timing). It must not use manual inspection of test logs or source code of individual tests. The approach should not require additional infrastructure beyond what is typically logged in CI systems.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The dataset is large but publicly constructable from the OpenStack Gerrit API, although collecting it requires significant API crawling effort. A replication package may provide preprocessed data, reducing setup burden. Model fitting requires only moderate computational resources (a standard CPU for logistic regression or ensemble methods). The main challenge is ensuring that features are correctly computed from raw CI event data and that the evaluation follows proper temporal splits to avoid data leakage.

## Metadata

```
subfield: Automated Testing & Test Generation
venue: ASE 2025
year: 2025
difficulty: medium
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```