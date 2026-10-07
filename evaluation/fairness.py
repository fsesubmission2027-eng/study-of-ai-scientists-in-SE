"""Fair cross-tool score aggregation (excludes N/A axes from denominators)."""

from __future__ import annotations

from typing import Any


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def build_fair_scores(results: dict[str, Any]) -> dict[str, Any]:
    """Build dashboard scores that only average applicable axes."""
    applicable: list[str] = []
    skipped: list[dict[str, str]] = []
    numeric: list[float] = []

    comp = results.get("completeness") or {}
    if comp.get("status") == "not_applicable":
        skipped.append({"axis": "completeness", "reason": comp.get("reason", "n/a")})
    elif comp.get("required_score") is not None:
        applicable.append("completeness")
        numeric.append(float(comp["required_score"]))

    ig = results.get("idea_generation") or {}
    st = ig.get("status")
    if st in {"missing_idea", "not_applicable"}:
        skipped.append({"axis": "idea_generation", "reason": st})
    elif ig.get("overall_score") is not None and st == "ok":
        applicable.append("idea_generation")
        numeric.append(float(ig["overall_score"]) / 5.0)

    pr = results.get("peer_review") or {}
    if pr.get("status") in {"missing_review_report", "not_provided"}:
        skipped.append({"axis": "peer_review", "reason": "optional_external_review"})
    elif pr.get("overall_score") is not None and pr.get("status") == "ok":
        applicable.append("peer_review")
        scale = str(pr.get("score_scale") or "1-5")
        if scale == "1-10":
            numeric.append(float(pr["overall_score"]) / 10.0)
        else:
            numeric.append(float(pr["overall_score"]) / 5.0)

    al = results.get("alignment") or {}
    if al.get("status") in {"missing_task_dir", "llm_skipped"}:
        skipped.append({"axis": "alignment", "reason": al.get("status", "n/a")})
    elif al.get("overall_alignment_score") is not None:
        applicable.append("alignment")
        numeric.append(float(al["overall_alignment_score"]))

    lit = results.get("literature_review") or {}
    if lit.get("status") in {"not_applicable", "missing_agent_references"}:
        skipped.append({"axis": "literature_review", "reason": lit.get("status", "n/a")})
    else:
        fab = (lit.get("fabrication") or {}).get("fabrication_rate")
        cov = (lit.get("coverage") or {}).get("recall")
        rec = ((lit.get("recency") or {}).get("windows") or {}).get("3", {}).get("recent_ratio")
        parts = [x for x in (fab, cov, rec) if isinstance(x, (int, float))]
        if parts:
            applicable.append("literature_review")
            # Lower fabrication is better → invert for aggregate
            lit_vals = []
            if isinstance(fab, (int, float)):
                lit_vals.append(max(0.0, 1.0 - float(fab)))
            if isinstance(cov, (int, float)):
                lit_vals.append(float(cov))
            if isinstance(rec, (int, float)):
                lit_vals.append(float(rec))
            if lit_vals:
                numeric.append(sum(lit_vals) / len(lit_vals))

    ea = results.get("experiment_analysis") or {}
    sc = ea.get("scores") or {}
    ea_parts: list[float] = []
    if sc.get("experiment_success") is True:
        ea_parts.append(1.0)
    elif sc.get("experiment_success") is False:
        ea_parts.append(0.0)
    for key in ("idea_code_score", "results_paper_score"):
        v = sc.get(key)
        if isinstance(v, (int, float)):
            ea_parts.append(float(v) / 5.0)
    cov = sc.get("setup_coverage")
    if isinstance(cov, (int, float)):
        ea_parts.append(float(cov))
    if ea_parts:
        applicable.append("experiment_analysis")
        numeric.append(sum(ea_parts) / len(ea_parts))

    return {
        "applicable_axes": applicable,
        "skipped_axes": skipped,
        "fair_mean_0_1": round(_mean(numeric), 4) if numeric else None,
        "note": (
            "fair_mean_0_1 averages only applicable axes; optional peer review and "
            "framework-inapplicable literature are excluded from the denominator."
        ),
    }
