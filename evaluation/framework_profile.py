"""Per-framework expectations for fair, comparable evaluation.

Fairness rule: only score gates/axes that apply to the detected framework;
use framework-native artifact paths before generic globs; treat missing optional
inputs as ``not_applicable`` rather than failure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from paths import _load_manifest, detect_framework


@dataclass(frozen=True)
class FrameworkProfile:
    key: str
    # Benchmark gates counted in completeness (paper = tex OR pdf).
    required_gates: tuple[str, ...] = ("idea", "code", "results", "paper")
    literature_applicable: bool = True
    # Ordered result paths to try before generic discovery.
    result_candidates: tuple[str, ...] = ()
    result_text_candidates: tuple[str, ...] = ()
    idea_priority: tuple[str, ...] = ()


PROFILES: dict[str, FrameworkProfile] = {
    "aris": FrameworkProfile(
        key="aris",
        result_candidates=(
            "results/metrics.json",
            "experiment_results/metrics.json",
            "project/metrics.json",
            "artifacts/results/metrics.json",
        ),
        idea_priority=("idea-stage/IDEA_REPORT.md", "idea-stage/selected_idea.md"),
    ),
    "evoscientist": FrameworkProfile(
        key="evoscientist",
        result_candidates=(
            "results/metrics.json",
            "results/metrics_summary.json",
            "results/grid/metrics_summary.json",
            "artifacts/results/metrics_summary.json",
            "artifacts/results/metrics.json",
        ),
        idea_priority=(
            "idea-stage/selected_idea.md",
            "idea-stage/IDEA_REPORT.md",
            "plan.md",
            "todos.md",
        ),
    ),
    "deepscientist": FrameworkProfile(
        key="deepscientist",
        result_candidates=(
            "**/eval_output*/results.json",
            "**/.ds/worktrees/**/eval_output*/results.json",
            "**/.ds/worktrees/**/experiments/**/output/*.json",
            "**/quests/**/experiments/**/output/*.json",
            "artifacts/reports/*.json",
            "**/artifacts/reports/*.json",
            "**/expogen/**/results.json",
            "results/results.json",
            "results/analysis.json",
            "artifacts/results/results.json",
        ),
        idea_priority=(
            "artifacts/idea/selected_idea.md",
            "artifacts/idea.json",
            "DeepScientist/quests/001/idea.md",
            "idea.md",
        ),
    ),
    "researchclaw": FrameworkProfile(
        key="researchclaw",
        result_candidates=(
            "artifacts/results/run-1.json",
            "stage-12/runs/**/metrics.json",
            "stage-13/runs/**/metrics.json",
        ),
        idea_priority=("artifacts/idea.json",),
    ),
    "tiny_scientist": FrameworkProfile(
        key="tiny_scientist",
        result_text_candidates=(
            "experiment_results.txt",
            "artifacts/results/experiment_results.txt",
        ),
        result_candidates=("artifacts/results/metrics.json",),
        idea_priority=("artifacts/idea.json", "tiny_idea.json", "tiny_idea_from_think.json"),
    ),
    "ai_scientist": FrameworkProfile(
        key="ai_scientist",
        result_candidates=(
            "session/data/metrics.json",
            "artifacts/results/metrics.json",
            "**/research_summary.json",
            "**/draft_summary.json",
            "**/baseline_summary.json",
            "**/ablation_summary.json",
        ),
        idea_priority=("session/idea.json",),
    ),
    "airesearcher": FrameworkProfile(
        key="airesearcher",
        literature_applicable=False,
        result_candidates=("results/metrics.json", "results/results.json"),
        idea_priority=("artifacts/idea.json", "idea.md"),
    ),
    "unknown": FrameworkProfile(key="unknown"),
}


def get_framework_profile(run_dir: Path, manifest: dict[str, Any] | None = None) -> FrameworkProfile:
    fw = detect_framework(run_dir, manifest or _load_manifest(run_dir))
    return PROFILES.get(fw, PROFILES["unknown"])


# Documented fairness audit (what was unfair → fix).
FAIRNESS_AUDIT: list[dict[str, str]] = [
    {
        "axis": "completeness",
        "was_unfair": "Required both paper.tex AND paper.pdf; any tool missing one failed equally.",
        "fix": "Paper gate: PDF=1.0; TeX-only=0.5; ``complete`` requires PDF.",
    },
    {
        "axis": "completeness",
        "was_unfair": "``results`` counted stub/seed JSON (dataset_candidate/metrics.json).",
        "fix": "``results`` requires substantive numeric results via results_normalize.",
    },
    {
        "axis": "experiment_success",
        "was_unfair": "Only metrics.json; ignored results.json / experiment_results.txt.",
        "fix": "Framework-ordered result candidates + normalized loaders.",
    },
    {
        "axis": "literature_review",
        "was_unfair": "Penalized tools with no bib; airesearcher has no workspace references.",
        "fix": "literature_applicable=false → status not_applicable; excluded from fair aggregate.",
    },
    {
        "axis": "literature_review",
        "was_unfair": "related_work.json subset as gold made recall hard to interpret.",
        "fix": "Coverage gold is original paper REFERENCES from mineru; related_work only enriches metadata/fallback.",
    },
    {
        "axis": "peer_review",
        "was_unfair": "Missing Stanford report looked like evaluation failure.",
        "fix": "status not_provided; optional axis, never counts as tool failure.",
    },
    {
        "axis": "paths/find_results",
        "was_unfair": "Picked downloads/** and sandbox noise (e.g. airesearcher LLVM tree).",
        "fix": "Exclude downloads/, seeds/, dataset_candidate/, sandbox junk paths.",
    },
    {
        "axis": "paths/framework_noise",
        "was_unfair": "DeepScientist .deepscientist_npm / runtime / skills templates counted as code/paper/results.",
        "fix": "FRAMEWORK_NOISE_DIRS+markers; quest worktree + eval_output results; paper md drafts; reject template tex.",
    },
    {
        "axis": "paths/paper_tex",
        "was_unfair": "tiny_scientist / ACL runs store paper under latex/*.tex; evaluator only looked at paper/main.tex.",
        "fix": "latex/**/*.tex with substantive-body heuristic; find_paper_document uses same rules.",
    },
    {
        "axis": "literature_review",
        "was_unfair": "Entire custom.bib (300+ anthology entries) verified when paper had zero \\cite commands.",
        "fix": "collect_agent_references filters bib to in-text cite keys; skips uncited bulk bib (>40 entries).",
    },
    {
        "axis": "paths/ai_scientist_summaries",
        "was_unfair": "AI Scientist can persist substantive results and paper-like drafts in *_summary.json logs rather than paper/main.tex or results/**/*.json.",
        "fix": "Treat draft_summary/research_summary as weak paper documents and summary JSONs as result candidates.",
    },
    {
        "axis": "framework/ai_scientist_v2",
        "was_unfair": "Manifest framework ``ai_scientist_v2`` fell through to profile ``unknown``, skipping AI-Scientist idea/result path priorities.",
        "fix": "Normalize ``ai_scientist_v2`` (and common aliases) to profile key ``ai_scientist``.",
    },
    {
        "axis": "idea_generation",
        "was_unfair": "plan.md/todos.md weak proxies scored same as structured idea.json.",
        "fix": "Framework idea_priority tried first; missing idea → not_applicable where appropriate.",
    },
]
