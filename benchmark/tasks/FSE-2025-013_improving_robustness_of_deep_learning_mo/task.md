# Task: FSE-2025-013 — Improving Robustness of Deep Learning Models for Code by Mitigating Spurious Correlations

## Background

Deep learning models are increasingly applied to software engineering tasks such as defect detection, code classification, code translation, and code repair. However, adversarial attacks can severely degrade their performance, often reducing accuracy from over 90% to less than 10%. A root cause is that these models frequently learn spurious correlations between superficial syntactic patterns (e.g., variable naming) and predicted labels, rather than capturing the true causal relationships that determine program behavior. Existing defenses, including adversarial training and contrastive learning, extend the training distribution but do not systematically eliminate spurious correlations; they lack a theoretical foundation to distinguish causal features from spurious ones, and they have shown limited effectiveness against advanced attacks. There is a need for defense mechanisms that can identify and rely on semantically meaningful, causally relevant features of code.

## Research Question

How can spurious correlations between superficial code features and model predictions be eliminated to improve the robustness of deep learning models for software engineering tasks?

## Experiment Setup

### Datasets
```
- name: POJ-104
  source: https://github.com/microsoft/CodeBERT/tree/master/GraphCodeBERT/codesearch/poj-104/data
  description: 51,976 programs categorized into 104 distinct functionalities for function classification.
  access: open
- name: CodeChef
  source: https://github.com/zhangxinchen1996/CARROT
  description: 33,822 programs for defect detection, labeled as OK, WA, TLE, RE.
  access: open
- name: CodeTrans
  source: https://github.com/microsoft/CodeXGLUE/tree/main/Code-Code/code-to-code-trans
  description: 11,800 paired Java–C# functions for code translation.
  access: open
- name: Bugs2Fix
  source: https://github.com/microsoft/CodeXGLUE/tree/main/Code-Code/code-refinement
  description: 65,454 pairs of buggy and corrected Java functions for code repair.
  access: open
```

### Baselines
```
- name: CARROT-T
  reference: CARROT: An adversarial robustness evaluation toolkit for source code (USENIX Security 2022)
- name: ALERT-T
  reference: Adversarial training method for code models (see reference [46] in the original paper)
- name: ContraBERT
  reference: Contrastive learning approach for code representation (see reference [19] in the original paper)
- name: SemanticDefense
  reference: Prior defense method that leverages program semantics to eliminate spurious correlations (see original evaluation section for citation)
```

### Metrics
```
- name: Attack Success Rate (ASR)
  definition: Fraction of test examples where an adversarial attack causes the model to output an incorrect label (for classification) or significantly degrades output quality (for generation).
- name: Accuracy
  definition: Standard classification accuracy on clean (unattacked) test samples.
- name: CodeBLEU
  definition: A metric that evaluates generated code by comparing syntactic AST match, semantic data-flow match, and exact token overlap against a reference.
- name: Δ_drop
  definition: The difference between a model's CodeBLEU score before and after an adversarial attack, measuring robustness impact.
```

### Sub-questions
```
- RQ1: How effectively can the defense method reduce the success rate of adversarial attacks on code classification models?
- RQ2: To what extent does the defense cause the model to rely on causal features rather than spurious ones?
- RQ3: Which components of the defense strategy are most responsible for improving robustness?
- RQ4: Can the defense method be applied to code generation tasks (e.g., translation and repair) and still provide robustness?
```

### Target Subject

Pre-trained language models for source code (e.g., CodeBERT, GraphCodeBERT, StarCoder) fine-tuned on downstream tasks: function classification, defect detection, code translation, and code repair. Attacks include Metropolis-Hastings identifier renaming (MHM), CARROT (identifier manipulation and dead code insertion), and CodeAttack (black-box token manipulation).

### Constraints

Training dataset splits: classification 64%/20%/16% train/val/test; generation tasks use standard splits (e.g., 1000 test for translation, 5835 for repair). Attack evaluation: maximum 40 attack attempts per sample, repeated on a 20% uniform subset of the test set 5 times, averaging results. Models must be fine-tuned from publicly available pre-trained checkpoints. Training hyperparameters: Adam optimizer, batch size 64, max epochs 28-36, early stopping 3, learning rate 5e-5 (classification) / 5e-5 (generation). For generation, beam search with size 5-10. Defense must be model- and task-agnostic, without access to attack algorithms’ internals.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All datasets are openly available. Pre-trained model checkpoints (CodeBERT, GraphCodeBERT, StarCoder) are accessible from Hugging Face. Adversarial attack implementations (CARROT, MHM, CodeAttack) exist in open-source repositories, enabling reproducibility. Training and evaluation require multi-GPU setups (e.g., RTX A6000 48GB) and can take several hours to days per model/task due to large dataset sizes and repeated attack evaluations. The main technical challenge is designing a defense that effectively eliminates spurious feature reliance without prior knowledge of the attack type, while remaining compatible across different model architectures and task types.

## Metadata

```
subfield: AI/ML System Testing
venue: FSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```