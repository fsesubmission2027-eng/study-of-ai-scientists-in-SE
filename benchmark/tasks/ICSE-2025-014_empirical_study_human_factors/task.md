# Task: ICSE-2025-014 — [NOT SPECIFIED IN PAPER]

## Background

Mobile apps are a dominant software category, and their usability directly influences user satisfaction and market success. Conventional usability evaluation methods, such as lab-based usability testing and expert reviews, are effective but require substantial resources and expertise, making them difficult for small development teams to adopt systematically. Recent advances in Generative Artificial Intelligence, particularly Foundation Models capable of processing text, code, and images, have opened new possibilities for automating knowledge‑intensive tasks in software engineering. However, it remains unclear whether such models can meaningfully assist in detecting usability issues in real-world mobile app interfaces without compromising the rigour of established human‑centred methods. This work investigates the potential of GenAI to support or partially automate usability evaluation for native mobile apps.

## Research Question

To what extent can a Generative AI approach identify usability issues in mobile app user interfaces, and how does its performance compare with conventional usability evaluation methods?

## Experiment Setup

### Datasets
```
- name: Mobile App Usability Evaluation Dataset
  source: Two open-source iOS apps (a quiz app and a to-do app) written in SwiftUI, along with their UI screenshots and a set of ground-truth usability issues identified through expert reviews and usability testing. The apps were selected from GitHub by searching for SwiftUI projects of medium complexity. A replication package containing source code, screenshots, and usability issues is available (contact authors).
  description: Four-view quiz app and two-view to-do app, each with typical user tasks. Ground truth includes usability issues aggregated from expert reviews and think-aloud usability tests with 10 participants per app.
  access: open (replication package upon request; similar apps constructable from GitHub)
```

### Baselines
```
- name: Usability Testing with Think-Aloud Protocol
  reference: Nielsen, J. (1994). Usability Engineering. Morgan Kaufmann.
- name: Expert Review
  reference: Usability inspection method performed by UI/UX professionals.
```

### Metrics
```
- name: Precision
  definition: Proportion of usability issues flagged by the tool that are true issues, as validated by usability experts against the ground truth.
- name: Recall
  definition: Proportion of all actual usability issues (union of issues from expert reviews and usability testing) that the tool successfully identifies.
```

### Sub-questions
```
- RQ1: How accurately can the GenAI-powered tool predict usability issues in mobile apps?
- RQ2: How do the predicted issues compare with those identified by traditional usability evaluation methods, and to what extent can the tool replace them?
- RQ3: How would an app development team perceive the support of such a tool during development?
```

### Target Subject

Native iOS mobile apps of medium complexity, written in SwiftUI, such as a quiz app and a to-do app. The evaluation also includes a third app (transit app for visually impaired persons) used in a qualitative focus group.

### Constraints

The tool may use app source code and UI screenshots as input, but must not rely on pre-existing bug databases or user reviews. Evaluation must be conducted on apps not seen during any tool development. Ground-truth usability issues must be established through human-centred methods (usability testing with real users executing predefined tasks, and independent expert reviews). The same apps must be evaluated by all methods for fair comparison.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The required dataset of open-source apps and manually labelled usability issues is available via a replication package, but obtaining it may require contacting the authors. Replicating the full user study (10 participants per app) and expert reviews is time- and resource-intensive. However, the core tool evaluation (precision, recall) can be performed using the provided ground truth without re-running the human studies. Access to a commercial LLM (e.g., GPT‑4) is necessary for generating predictions. The qualitative focus group with a development team adds an additional layer of logistical effort but is not mandatory for reproducing the quantitative results.

## Metadata

```
subfield: Empirical Study & Human Factors
venue: ICSE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```