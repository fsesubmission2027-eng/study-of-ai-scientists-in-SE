"""Completeness evaluation for AI-scientist benchmark runs (framework-fair)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from framework_profile import get_framework_profile
from paths import (
    detect_framework,
    find_bonus,
    find_code,
    find_idea,
    find_paper_md,
    find_paper_json,
    find_pdf,
    find_results,
    find_tex,
    _load_manifest,
)
from results_normalize import normalize_results

REQUIRED_GATES = ("idea", "code", "results", "paper")
BONUS_WEIGHT = {
    "experiment_plan": 0.04,
    "experiment_log": 0.03,
    "review": 0.04,
    "readme": 0.02,
    "narrative": 0.02,
    "bib": 0.02,
}


def _artifact_dict(art: Any) -> dict[str, Any] | None:
    if art is None:
        return None
    return {
        "path": art.relative,
        "bytes": art.bytes,
        "via": art.via,
    }


def _metrics_keys_from_normalized(norm: Any) -> list[str]:
    if norm.data is None or not isinstance(norm.data, dict):
        return []
    return [str(k) for k in norm.data.keys()][:40]


def evaluate_completeness(run_dir: Path, *, task_dir: Path | None = None) -> dict[str, Any]:
    """Score required artifacts with framework-fair gates."""
    run_dir = run_dir.resolve()
    manifest = _load_manifest(run_dir)
    framework = detect_framework(run_dir, manifest)
    profile = get_framework_profile(run_dir, manifest)

    idea = find_idea(run_dir, priority=profile.idea_priority)
    code = find_code(run_dir)
    norm = normalize_results(run_dir, profile=profile)
    tex = find_tex(run_dir)
    pdf = find_pdf(run_dir, auto_compile=True)
    paper_md = find_paper_md(run_dir)
    paper_json = find_paper_json(run_dir)
    bonus = find_bonus(run_dir)
    results_arts = find_results(run_dir)

    results_ok = norm.status == "ok" and norm.numeric_leaf_count >= 3
    # Paper: PDF = full credit; TeX or substantial markdown draft = half; neither = zero.
    if pdf is not None:
        paper_score = 1.0
        paper_status = "pdf"
    elif tex is not None:
        paper_score = 0.5
        paper_status = "tex_only"
    elif paper_md is not None:
        paper_score = 0.5
        paper_status = "md_only"
    elif paper_json is not None:
        paper_score = 0.5
        paper_status = "json_only"
    else:
        paper_score = 0.0
        paper_status = "missing"

    gate_scores = {
        "idea": 1.0 if idea is not None else 0.0,
        "code": 1.0 if len(code) > 0 else 0.0,
        "results": 1.0 if results_ok else 0.0,
        "paper": paper_score,
    }
    missing = [name for name, sc in gate_scores.items() if sc <= 0.0]
    # 「完整」= 四项都有，且论文至少是 PDF（TeX 只有一半分，不算完整交付）。
    complete = all(gate_scores[k] >= 1.0 for k in REQUIRED_GATES)

    required_score = sum(gate_scores.values()) / float(len(REQUIRED_GATES))

    bonus_hits = {k: v is not None for k, v in bonus.items()}
    bonus_score = 0.0
    for key, weight in BONUS_WEIGHT.items():
        if bonus_hits.get(key):
            bonus_score += weight
    bonus_score = min(1.0, bonus_score)

    if not complete:
        overall = round(required_score * 0.8, 4)
    else:
        overall = round(min(1.0, 0.83 + bonus_score * 0.17), 4)

    return {
        "framework": framework,
        "run_dir": str(run_dir),
        "task_dir": str(task_dir) if task_dir else None,
        "complete": complete,
        "required_score": round(required_score, 4),
        "bonus_score": round(bonus_score, 4),
        "overall_score": overall,
        "missing": missing,
        "required": {
            "idea": _artifact_dict(idea),
            "code": {
                "count": len(code),
                "files": [_artifact_dict(c) for c in code[:30]],
            },
            "results": {
                "substantive": results_ok,
                "normalized_path": norm.relative or None,
                "numeric_leaf_count": norm.numeric_leaf_count,
                "discovered_files": [_artifact_dict(r) for r in results_arts[:20]],
                "metrics_keys_sample": _metrics_keys_from_normalized(norm),
            },
            "paper": {
                "tex": _artifact_dict(tex),
                "pdf": _artifact_dict(pdf),
                "md": _artifact_dict(paper_md),
                "json": _artifact_dict(paper_json),
                "status": paper_status,
                "score": paper_score,
            },
        },
        "bonus": {k: _artifact_dict(v) for k, v in bonus.items()},
        "manifest_status": manifest.get("status"),
        "gate_scores": gate_scores,
        "fairness": {
            "gates": list(REQUIRED_GATES),
            "paper_gate_rule": "PDF=1.0; TeX-only/md_only/json_only=0.5; complete requires PDF",
            "results_gate_rule": "substantive numeric results via framework-aware normalize_results",
            "audit_ref": "framework_profile.FAIRNESS_AUDIT",
        },
        "notes": [
            "Required: idea, code, substantive results, paper (PDF full; TeX/markdown/JSON draft half).",
            "Stub/seed metrics (e.g. dataset_candidate/metrics.json) do not satisfy results.",
            "Framework noise (.deepscientist_npm, skills/templates, runtime) is excluded from code/results/paper.",
            "Manifest status is informational; disk presence is authoritative.",
        ],
    }
