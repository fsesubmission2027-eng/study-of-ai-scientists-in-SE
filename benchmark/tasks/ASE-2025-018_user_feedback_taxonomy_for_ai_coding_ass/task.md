# Task: ASE-2025-018 — User Feedback Taxonomy for AI Coding Assistants from VS Code Marketplace

## Background

AI coding assistants are widely adopted by developers, but verifying their suggestions can consume more than half of coding time, underscoring the need to understand user perceptions. Existing studies rely on small-scale interviews, surveys, or focused investigations that miss the broader ecosystem and subjective experiences. Online marketplace reviews offer large-scale, unsolicited feedback from a diverse user base, yet prior review mining studies have focused exclusively on GitHub Copilot, used taxonomies derived from advanced user bug reports, and overlooked the voices of novice and non‑technical users. The Visual Studio Code Marketplace hosts a rapidly growing set of AI coding assistants with extensive user reviews, creating an opportunity to comprehensively analyze what users discuss, value, and dislike across multiple tools.

## Research Question

What aspects of AI coding assistants do users discuss in their marketplace reviews, and what sentiments do they express toward these aspects?

## Experiment Setup

### Datasets
```
- name: VS Code Marketplace AI Assistant Reviews
  source: Visual Studio Code Marketplace; extensions can be filtered by AI-related tags or descriptions. Reviews are publicly accessible via web scraping.
  description: A set of 5,259 user reviews (after filtering out reviews shorter than 10 words) from 32 popular AI coding assistant extensions. A stratified random sample of 361 reviews was manually annotated with topic labels and sentiment (like, dislike, neutral) through a bottom‑up taxonomy construction process. Non‑English reviews were translated to English.
  access: constructable
```

### Baselines
```
[NOT SPECIFIED IN PAPER]
```

### Metrics
```
- name: Inter‑rater agreement (Cohen’s Kappa)
  definition: Measures the agreement between two independent annotators on topic and sentiment labels, computed on a subset of reviews.
- name: Category frequency
  definition: Count and percentage of reviews or labels assigned to each leaf node or top‑level category in the taxonomy.
- name: Sentiment distribution
  definition: Proportion of labels expressing like, dislike, or neutral sentiment for each category or overall.
```

### Sub-questions
```
- RQ1: What topics do users discuss about AI coding assistants?
- RQ2: What aspects of AI coding assistants do users care about, appreciate, and dislike, and what does this reveal about their preferences?
```

### Target Subject

User reviews of AI coding assistant extensions on the Visual Studio Code Marketplace. Example assistants include GitHub Copilot, Tabnine, Codeium, and Amazon CodeWhisperer.

### Constraints

Only reviews with at least 10 words are considered; non‑English reviews must be translated. The set of extensions studied must be among the most installed or have a high review count to represent widely used tools. Annotation must ensure inter‑rater reliability (e.g., Cohen’s Kappa ≥ 0.8). Only publicly available review data may be used.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The review data is publicly accessible via web scraping from the Visual Studio Code Marketplace, though rate limits may apply. Manual annotation of 361 reviews is labor‑intensive (estimated 40–60 hours for a pair of annotators) but feasible for a research team. No specialized compute resources are required. Achieving high inter‑rater agreement may demand multiple iterative coding rounds.

## Metadata

```
subfield: Empirical Study & Human Factors
venue: ASE 2025
year: 2025
difficulty: medium
paper_type: empirical
award: ACM SIGSOFT Distinguished Paper Award
```