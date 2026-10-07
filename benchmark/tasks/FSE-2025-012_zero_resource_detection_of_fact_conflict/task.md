# Task: FSE-2025-012 — Zero-Resource Detection of Fact-Conflicting Hallucinations in LLM Outputs Without External Resources or Token Probabilities

## Background

Large Language Models (LLMs) frequently produce fact-conflicting hallucinations—coherent but factually incorrect responses—that pose risks for applications requiring high factual accuracy. Existing detection methods often rely on external databases or search engines, which limits their use in domains without comprehensive knowledge bases. Other methods depend on token-level confidence metrics, which are inaccessible for closed-source models like GPT-4. SelfCheckGPT, a state-of-the-art zero-resource approach, generates multiple reference samples and checks consistency; however, it tends to produce samples identical to the original response, significantly reducing its effectiveness. This highlights a need for a more reliable self-contained hallucination detection technique that operates solely using the LLM itself, without external resources or internal probability information, and that can overcome the duplicate-sample limitation of current sample-based methods.

## Research Question

How can a hallucination detection method for LLMs operate without external knowledge bases or token-level probabilities, and effectively overcome the issue of identical sample generation that hampers existing self-contained techniques?

## Experiment Setup

### Datasets
```
- name: TruthfulQA-Enhanced
  source: Available from the paper's artifact repository (updated benchmark with 238 corrected answers)
  description: An enhanced version of the TruthfulQA dataset containing 817 questions across 38 categories; 238 entries were manually updated with corrected answers to address missing or outdated reference answers.
  access: open
- name: HotpotQA (subset)
  source: https://hotpotqa.github.io/
  description: A multi-hop question-answering dataset; a random subset of 610 questions was used to manage token consumption, focusing on comparative reasoning questions.
  access: open
- name: FreshQA (subset)
  source: https://github.com/alexandrasouly/freshqa
  description: A QA dataset requiring up-to-date knowledge; 155 questions dated before 2023 were selected to avoid post-training knowledge gaps.
  access: open
```

### Baselines
```
- name: SelfCheckGPT
  reference: Potsawee Manakul et al., SelfCheckGPT: Zero-Resource Black-Box Hallucination Detection for Generative Large Language Models, EMNLP 2023. GitHub: https://github.com/potsawee/selfcheckgpt
```

### Metrics
```
- name: Precision
  definition: The proportion of responses flagged as hallucinations that are indeed factually incorrect.
- name: Recall
  definition: The proportion of actual hallucinated responses that are correctly identified as such.
- name: F1-score
  definition: The harmonic mean of precision and recall.
```

### Sub-questions
```
- RQ1: How does the detection performance compare to SelfCheckGPT in terms of precision, recall, and F1-score across different LLMs and datasets?
- RQ2: What is the effect of the LLM's temperature setting on the effectiveness of hallucination detection?
- RQ3: How consistent is the detection performance across multiple independent runs?
```

### Target Subject

Both closed-source and open-source large language models, specifically GPT-4o, GPT-3.5-turbo, Llama3-8B, and Mistral-7B.

### Constraints

The detection method must not use any external databases, search engines, or fact-verification APIs. It must not rely on internal model probability outputs (e.g., token logits), as these may be inaccessible for closed-source models. The approach must be self-contained, leveraging only the LLM's own text generation capabilities.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

TruthfulQA-Enhanced is publicly available via the paper's artifact repository; HotpotQA and FreshQA are also open. Running open-source models (Llama3-8B, Mistral-7B) requires an NVIDIA A100 40GB GPU, while closed-source models need OpenAI API access. The evaluation spans 1,582 questions across three datasets, with manual verification used to establish ground-truth labels—this step is resource-intensive but can be partially automated. Overall experiments are feasible but computationally demanding.

## Metadata

```
subfield: AI/ML System Testing
venue: FSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```