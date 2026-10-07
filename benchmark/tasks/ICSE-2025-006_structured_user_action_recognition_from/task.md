# Task: ICSE-2025-006 — Structured User Action Recognition from Application Screencasts

## Background

UI automation is crucial for software testing, bug reproduction, and robotic process automation. Current record-and-replay tools typically rely on operating system accessibility support, GUI framework instrumentation, or application source code, making them intrusive and limited in applicability. A non-intrusive alternative is to reverse-engineer user actions from screen recordings, but this requires recognizing structured actions—each consisting of a command, a target widget, and a location—from video fragments. While video segmentation and widget detection have been studied, an effective technique to generate human-understandable structured action descriptions from screencast clips is still missing, preventing the realization of a complete non-intrusive pipeline.

## Research Question

How can a system automatically recognize and describe human-computer interaction actions (command, widget type, and location) from short video fragments of application screencasts, without relying on application source code, OS accessibility APIs, or GUI framework instrumentation?

## Experiment Setup

### Datasets
```
- name: Multi-app screencast dataset
  source: Constructed from YouTube how-to videos and bug report screencasts; no direct public download available. Detailed collection and labeling protocols are described in the paper; replication involves downloading ~288 videos from YouTube and Firefox Bugzilla, then manually segmenting and labeling 7,260 action fragments.
  description: 12.8 hours of screencasts across five desktop applications (web browser, word processor, graphics editor, video conference, system settings) labeled with 7,260 structured action descriptions (11 command classes, 11 widget classes, free-form location phrases).
  access: constructable
```

### Baselines
```
- name: Not specified
  reference: [NOT SPECIFIED IN PAPER]
```

### Metrics
```
- name: Command classification accuracy / precision / recall / F1
  definition: Percentage of correctly predicted command labels out of all test fragments, plus per-class and macro-averaged precision, recall, and F1-score.
- name: Widget classification accuracy / precision / recall / F1
  definition: Percentage of correctly predicted widget labels out of all test fragments, plus per-class and macro-averaged precision, recall, and F1-score.
- name: BLEU-1
  definition: 1-gram BLEU score comparing the generated location phrase to the human reference, measuring precision of word overlap.
- name: ROUGE-1
  definition: 1-gram ROUGE score measuring recall of words in the generated location phrase against the reference.
- name: METEOR
  definition: METEOR score for the location phrase, combining precision, recall, and synonym/stemming matching.
- name: CIDEr
  definition: CIDEr score weighted by TF-IDF to capture the importance of words in the location phrase.
```

### Sub-questions
```
- RQ1: How accurately can structured user actions (command, widget, and location) be recognized from action screencasts?
- RQ2: How robust is the recognition to variations in application type, screen resolution, and operating system?
- RQ3: How does the method compare to alternative approaches, such as generic video captioning or single-frame classification baselines?
```

### Target Subject

Desktop application usage screencasts from diverse domains: web browsing (e.g., Firefox), document editing (e.g., Microsoft Word), graphics editing (e.g., Adobe Photoshop), video conferencing (e.g., Zoom), and system configuration (e.g., Windows 10 Settings).

### Constraints

The method must be non-intrusive: it cannot use application source code, OS internal APIs, GUI framework accessibility hooks, or dynamic instrumentation. Only the raw screencast video is available as input. The approach should work across different operating systems (Windows, Linux, macOS) and screen resolutions without application-specific tuning.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The dataset must be constructed by scraping publicly available videos and manual labeling, which is time-consuming but feasible with the described annotation tool. Training video-based deep learning models requires a GPU with sufficient memory for 3D CNNs; estimated training time is not provided but typical for video tasks. The primary challenge lies in the diverse appearance of widgets and the open-ended generation of location phrases from ambiguous visual contexts.

## Metadata

```
subfield: Automated Testing & Test Generation
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```