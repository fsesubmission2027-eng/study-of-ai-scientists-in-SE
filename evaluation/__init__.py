"""Automated evaluation for AI-scientist benchmark runs.

Axes:
  1. completeness — required artifacts + bonus
  2. idea_generation — idea artifact LLM scores (novelty vs Solution Space / feasibility / clarity)
  3. peer_review — Stanford APR downloaded report + LLM dimension scores
  4. alignment — mineru_sections.json claims/SOTA vs agent paper/metrics
  5. literature_review — fabrication / coverage recall / recency
  6. experiment_analysis — success, idea↔code, setup coverage, results↔paper
"""

from .completeness import evaluate_completeness
from .experiment_analysis import evaluate_experiment_analysis
from .idea_generation import evaluate_idea_generation
from .literature_review import evaluate_literature_review
from .paper_alignment import evaluate_paper_alignment
from .peer_review import evaluate_peer_review

__all__ = [
    "evaluate_completeness",
    "evaluate_idea_generation",
    "evaluate_experiment_analysis",
    "evaluate_peer_review",
    "evaluate_paper_alignment",
    "evaluate_literature_review",
]
