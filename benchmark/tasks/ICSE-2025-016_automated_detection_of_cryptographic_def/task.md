# Task: ICSE-2025-016 — Automated Detection of Cryptographic Defects in Ethereum Smart Contracts

## Background

Cryptography is increasingly used in Ethereum smart contracts via official system APIs to implement tasks like digital signatures and Merkle proofs, with over 10% of transactions relying on these APIs. However, smart contract developers often lack cryptographic expertise, leading to implementation defects that compromise security guarantees. Existing security tools for smart contracts focus on generic programming errors (e.g., reentrancy, integer overflow) and do not address crypto-specific flaws. As a result, cryptographic defects remain a prevalent but undetected threat. There is a need for a systematic understanding and automated detection of such defects to secure on-chain applications.

## Research Question

How can cryptographic defects in Ethereum smart contracts be automatically detected, and what is the prevalence of such defects in real-world contracts?

## Experiment Setup

### Datasets
```
- name: Crypto-related Smart Contracts Dataset
  source: Constructable from Ethereum blockchain replay (blocks 1 to 15,500,000) and Etherscan; a pre-collected version is available from the authors of the original study upon request.
  description: 25,745 Ethereum smart contracts that invoke at least one official Ethereum cryptographic API (e.g., ECRECOVER), including their source code, ABI, and up to 500 historical transactions per contract.
  access: restricted
```

### Baselines
```
- name: Manual ground truth
  reference: Human expert annotation of a random sample of contracts
```

### Metrics
```
- name: Precision
  definition: The fraction of tool-reported defects that are true positives.
- name: Recall
  definition: The fraction of true defects (from a manually annotated sample) that are detected by the tool.
- name: Prevalence
  definition: The proportion of smart contracts in the dataset that contain at least one cryptographic defect.
```

### Sub-questions
```
- RQ1: What is the precision of the detection approach on the large-scale dataset?
- RQ2: What is the recall of the approach measured against a manually annotated sample?
- RQ3: What is the prevalence and distribution of cryptographic defects in real-world smart contracts?
```

### Target Subject

Ethereum smart contracts that use cryptographic APIs for on-chain operations, such as contracts implementing digital signature verification, Merkle proof validation, random number generation, or message digest usage.

### Constraints

Only smart contracts with publicly available source code and ABI can be analyzed. The detection approach must operate without modifying the Ethereum protocol or execution environment, using only available on-chain data and source code.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

Constructing the dataset requires running an Ethereum archive node and replaying over 1.7 billion transactions, which demands substantial storage (multiple TB) and weeks of processing time. A pre-built dataset may be available from the original study's authors. The detection tool requires deep domain knowledge of both cryptography and smart contract semantics. Model training or fuzzing may be time-consuming; original experiments consumed 408 CPU hours on a high-memory server. Manual labeling for recall evaluation requires cryptographic expertise and is labor-intensive.

## Metadata

```
subfield: Software Security
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```