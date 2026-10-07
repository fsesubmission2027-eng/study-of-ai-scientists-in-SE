# Task: ASE-2025-015 — Improving Answer Quality in RAG-based Chatbots for Cloud Operational Queries

## Background

Cloud platforms like Azure and AWS offer hundreds of services with extensive documentation, making it difficult for engineers to quickly find actionable guidance. Keyword-based search returns lengthy documents that require manual filtering, while large language models (LLMs) may generate plausible but incorrect answers when proprietary knowledge is absent. Retrieval-Augmented Generation (RAG) addresses this by retrieving relevant knowledge to ground LLM responses, but deploying reliable RAG chatbots for cloud operations remains challenging. Real-world usage reveals that queries from cloud operators are often incomplete, out-of-scope, or semantically ambiguous, and critical knowledge may be missing from the document collection, leading to many incorrect or incomplete answers.

## Research Question

How can a Retrieval-Augmented Generation (RAG) chatbot effectively answer cloud operational queries that are frequently incomplete, diverse in intent, and may lack coverage in the available documents?

## Experiment Setup

### Datasets
```
- name: Team A Product Manual Queries
  source: Internal deployment at a cloud vendor (not publicly available)
  description: 300 real-world user queries related to product manuals of one service, collected from an external operations team.
  access: restricted
- name: Team B Product Manual Queries
  source: Internal deployment at a cloud vendor (not publicly available)
  description: 1,350 real-world user queries related to product manuals of another service, collected from internal operations teams.
  access: restricted
- name: Team C Incident/Failure Log Queries
  source: Internal deployment at a cloud vendor (not publicly available)
  description: 350 real-world user queries based on incident tickets and failure logs, collected from an on-call engineers team.
  access: restricted
```

### Baselines
```
- name: Standard RAG Chatbot
  reference: Uses LangChain (https://github.com/langchain-ai/langchain) with FAISS vector store (https://github.com/facebookresearch/faiss), BGE-M3 embeddings (https://huggingface.co/BAAI/bge-m3), bce-reranker-base (https://huggingface.co/maidalun1020/bce-reranker-base_v1), and Qwen2.5-32B LLM (https://huggingface.co/Qwen/Qwen2.5-32B), chunk size 100 tokens, top-5 retrieved chunks.
```

### Metrics
```
- name: Answer Accuracy
  definition: Proportion of queries for which the generated response is judged as fully correct and complete by human evaluators, based on the query's information need.
```

### Sub-questions
```
- RQ1: What categories of intents do cloud operators express in their queries?
- RQ2: How well does a standard RAG chatbot answer each intent category?
- RQ3: What are the main causes of failures across the RAG pipeline (query, retrieval, generation) and how do they relate to query intents?
```

### Target Subject

Cloud operational question answering systems, with queries from engineers managing cloud services—for example, queries about product manuals, incident diagnosis, troubleshooting steps, terminology explanation, or summarization of operational topics.

### Constraints

The solution must operate entirely within the organization's private infrastructure to protect proprietary documentation; no external API calls are permitted. Response time should not significantly exceed typical interactive chatbot latency (e.g., under 30 seconds). Only open-source LLMs and tools are used to avoid data leakage.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The real-world datasets are proprietary and not publicly available; reproducing the study requires access to internal cloud documentation and deployment of a chatbot to collect queries. Annotation requires expert cloud operators, which is resource-intensive. Running the LLM (Qwen2.5-32B) necessitates high-end GPU hardware (e.g., one A100) and inference optimization.

## Metadata

```
subfield: AIOps & System Reliability
venue: ASE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```