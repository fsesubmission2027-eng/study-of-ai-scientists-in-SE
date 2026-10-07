# Task: ICSE-2025-003 — Automated Accessibility Issue Report Generation from User Test Session Transcripts

## Background

Ensuring software accessibility for users with disabilities is critical, as over 1.3 billion people worldwide live with some form of disability, yet many web and mobile applications remain inaccessible. While automated accessibility testing tools and manual developer testing exist, they consistently miss issues that are discovered only through user testing with people who have disabilities. User testing is the most comprehensive evaluation method, but it is rarely adopted due to practical barriers such as the time-consuming process of manually reviewing long video recordings and producing structured test reports. Automating the report generation phase could significantly lower the cost and effort of accessibility user testing, but this requires a system that can understand natural language transcripts, identify accessibility barriers mentioned by testers, and compile them into accurate, timestamped issue descriptions. Existing approaches for automated test report generation do not address this complex natural language understanding task involving domain-specific accessibility knowledge and diverse assistive technology usage.

## Research Question

How can a system automatically generate accurate test reports from transcripts of accessibility user testing sessions, capturing all issues raised by testers with disabilities?

## Experiment Setup

### Datasets
```
- name: App-MM
  source: Open source Android app (Money Manager) with manually injected accessibility issues; ground truth transcripts and issue annotations from user testing sessions available from the paper authors upon request.
  description: A mobile finance tracking application modified to contain known accessibility barriers. 10 test sessions conducted by blind screen reader users.
  access: restricted
- name: App-GS
  source: Publicly accessible educational website for accessibility training (Record a Goose Sighting) with pre-injected issues; transcripts and ground truth from the paper authors.
  description: A web application designed to help people learn accessibility testing. 10 test sessions covering screen readers, alternative navigation, and screen magnifiers.
  access: restricted
- name: App-FB
  source: Proprietary archive of user testing sessions from Fable's crowdtesting platform; access restricted to the paper authors.
  description: 16 archival test sessions for a digital product by Fable, involving blind, low-vision, and limited-mobility testers using various assistive technologies.
  access: restricted
```

### Baselines
```
- name: Manual Report Generation
  reference: Standard industry practice where human accessibility analysts review test session recordings and compile issue reports.
```

### Metrics
```
- name: Recall
  definition: The proportion of all ground-truth accessibility issues that are correctly identified by the automated approach.
- name: Precision
  definition: The proportion of issues reported by the automated approach that match actual ground-truth issues (i.e., are true positives).
```

### Sub-questions
```
- RQ1: What factors in prompt design, such as the inclusion of domain-specific guidelines, task descriptions, and input structure, influence the ability of an LLM to detect accessibility issues from transcripts?
- RQ2: How accurate and consistent is the LLM-based report generation in terms of precision and recall across a diverse set of real-world user testing sessions?
- RQ3: What are the common failure modes and strengths of the LLM in this task, and what characteristics of the transcripts or test context lead to errors?
```

### Target Subject

Video-recorded accessibility user testing sessions involving participants with disabilities (blindness, low vision, motor impairments) using various assistive technologies (screen readers, alternative navigation, screen magnifiers) on mobile and web applications.

### Constraints

The approach must use only auto-generated transcripts (in .vtt format with timestamps and speaker labels) as input, along with optional contextual information such as task descriptions and assistive technology used. It must not require access to the original video or manual intervention during report generation. The LLM used should be a publicly available model (e.g., GPT-4.0).

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The annotated transcripts and ground truth issue sets are not publicly available and must be requested from the original authors. Alternatively, similar datasets can be constructed by conducting user testing on applications with known accessibility issues. Compute requirements are moderate, relying on API access to a large language model; processing 36 transcripts may incur notable cost and time. Technical challenges include ensuring reliable transcription quality and handling ambiguous or incomplete tester utterances, which are inherent to the testing sessions.

## Metadata

```
subfield: Automated Testing & Test Generation
venue: ICSE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```