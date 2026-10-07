"""Literature-review evaluation: fabrication, coverage recall, recency."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from framework_profile import get_framework_profile
from eval_layout import task_eval_dir
from literature_sources import (
    RefRecord,
    collect_agent_references,
    load_gold_references,
    match_ref_to_gold,
)
from literature_verify import LiteratureVerifier


def _year_of(ref: RefRecord, verified: dict[str, Any] | None = None) -> int | None:
    if verified:
        ry = verified.get("resolved_year")
        if isinstance(ry, int):
            return ry
        try:
            if ry is not None:
                return int(ry)
        except (TypeError, ValueError):
            pass
    return ref.year


def evaluate_literature_review(
    run_dir: Path,
    task_dir: Path | None = None,
    *,
    evals_root: Path | None = None,
    skip_verify: bool = False,
    as_of_year: int | None = None,
    recent_windows: tuple[int, ...] = (3, 5),
) -> dict[str, Any]:
    """Evaluate literature quality for one tool run.

    Metrics
    -------
    1. fabrication_rate among scholarly candidate refs (S2 + arXiv; tools/docs excluded)
    2. coverage vs original paper REFERENCES (mineru_sections.json):
       - recall (primary): |agent ∩ gold| / |gold|  where gold = original bibliography titles
       - intersection_size (secondary)
       - precision: |agent ∩ gold| / |agent|
    3. recency_ratio for last 3 and 5 years among refs with known year
    """
    run_dir = run_dir.resolve()
    profile = get_framework_profile(run_dir)
    as_of = as_of_year or datetime.now().year

    if not profile.literature_applicable:
        return {
            "run_dir": str(run_dir),
            "task_dir": str(task_dir) if task_dir else None,
            "status": "not_applicable",
            "framework": profile.key,
            "reason": "Framework does not produce workspace reference artifacts for fair comparison.",
            "scores": None,
        }

    agent_refs, sources_meta, collection_audit = collect_agent_references(run_dir)
    out: dict[str, Any] = {
        "run_dir": str(run_dir),
        "task_dir": str(task_dir) if task_dir else None,
        "status": "ok",
        "as_of_year": as_of,
        "agent_ref_count": len(agent_refs),
        "sources": sources_meta,
        "collection_audit": collection_audit,
        "fabrication": None,
        "coverage": None,
        "recency": None,
    }

    if not agent_refs:
        out["status"] = "not_applicable"
        if collection_audit.get("filter_mode") == "uncited_bulk_bib_skipped":
            out["reason"] = "uncited_bulk_bib_skipped"
            out["hint"] = (
                "Found a large .bib file but no \\cite keys in the paper TeX; "
                "bulk anthology/template bibliographies are not scored. "
                "Use literature_survey / related_work artifacts or cite papers in the manuscript."
            )
        else:
            out["reason"] = "no_reference_artifacts"
            out["hint"] = (
                "No literature artifacts found (bib / thebibliography / shortlist / related_work.txt / arxiv index). "
                "Marked not_applicable rather than failure — tool may not emit references in-run."
            )
        return out

    # --- 1) Fabrication / existence check ---
    verification_rows: list[dict[str, Any]] = []
    if skip_verify:
        out["fabrication"] = {
            "status": "skipped",
            "fake_count": None,
            "scholarly_count": None,
            "fabrication_rate": None,
        }
    else:
        cache_path = None
        override_path = None
        if task_dir is not None:
            tdir = task_eval_dir(task_dir, evals_root=evals_root)
            cache_path = tdir / "reference_verify_cache.json"
            override_path = tdir / "reference_verify_overrides.json"
        else:
            cache_path = run_dir / "artifacts" / "evaluation" / "reference_verify_cache.json"
            override_path = run_dir / "artifacts" / "evaluation" / "reference_verify_overrides.json"
        verifier = LiteratureVerifier(cache_path=cache_path, override_path=override_path)
        scholarly = 0
        fake = 0
        non_paper = 0
        verified_n = 0
        lookup_failed = 0
        insufficient = 0
        for ref in agent_refs:
            row = verifier.verify(ref)
            row["cite_key"] = ref.cite_key
            row["source_kind"] = ref.source_kind
            verification_rows.append(row)
            st = row.get("status")
            if st == "non_paper":
                non_paper += 1
            elif st == "verified":
                scholarly += 1
                verified_n += 1
            elif st == "lookup_failed":
                scholarly += 1
                lookup_failed += 1
            elif st == "insufficient_metadata":
                insufficient += 1
            elif st == "fabricated_or_unfound":
                scholarly += 1
                fake += 1
            else:
                scholarly += 1
                lookup_failed += 1
        verifier.save_cache()
        # Rate over conclusive scholarly checks only (exclude lookup_failed).
        conclusive = verified_n + fake
        rate = (fake / conclusive) if conclusive else None
        out["fabrication"] = {
            "status": "ok",
            "scholarly_count": scholarly,
            "verified_count": verified_n,
            "fake_count": fake,
            "lookup_failed_count": lookup_failed,
            "insufficient_metadata_count": insufficient,
            "non_paper_count": non_paper,
            "fabrication_rate": rate,
            "items": verification_rows,
            "cache_path": str(cache_path) if cache_path else None,
            "override_path": str(override_path) if override_path else None,
            "note": (
                "fabrication_rate = fake / (verified + fake). "
                "lookup_failed (API errors) and insufficient_metadata are excluded and retried or skipped. "
                "GitHub/docs/tool URLs are non_paper and excluded from the rate. "
                "To manually correct a false negative, edit reference_verify_overrides.json "
                "(key=normalized title / doi / cite_key; value=\"verified\" or a result dict), then re-run."
            ),
        }

    # --- 2) Coverage vs original paper REFERENCES (mineru) ---
    if task_dir is None:
        out["coverage"] = {"status": "missing_task_dir"}
    else:
        gold, gold_path = load_gold_references(task_dir)
        if not gold:
            out["coverage"] = {
                "status": "missing_gold",
                "hint": "Expected mineru_sections.json REFERENCES (or related_work.json fallback)",
            }
        else:
            matched_gold: list[str] = []
            matched_agent: list[str] = []
            for ref in agent_refs:
                g = match_ref_to_gold(ref, gold)
                if g is not None:
                    matched_gold.append(g.cite_key or g.title)
                    matched_agent.append(ref.cite_key or ref.title)
            # Unique gold hits
            uniq_gold = sorted(set(matched_gold))
            inter = len(uniq_gold)
            recall = inter / len(gold) if gold else None
            precision = inter / len(agent_refs) if agent_refs else None
            gold_is_mineru = "mineru_sections" in (gold_path or "")
            out["coverage"] = {
                "status": "ok",
                "gold_source": gold_path,
                "gold_count": len(gold),
                "gold_is_original_paper_references": gold_is_mineru,
                "gold_is_openalex_subset": not gold_is_mineru,
                "agent_count": len(agent_refs),
                "intersection_size": inter,
                "recall": recall,
                "precision": precision,
                "matched_gold_keys": uniq_gold[:100],
                "primary_metric": "recall",
                "note": (
                    "Primary metric is recall against the original paper bibliography "
                    "(titles from mineru_sections.json REFERENCES; related_work.json used "
                    "only to enrich DOI/year or as fallback if mineru titles are empty). "
                    "Denominator = |original paper references|. "
                    "Precision is secondary (agent may cite valid extra papers)."
                ),
            }

    # --- 3) Recency ---
    year_map: dict[int, int] = {}
    unknown_year = 0
    for idx, ref in enumerate(agent_refs):
        verified = verification_rows[idx] if idx < len(verification_rows) else None
        # Skip non-paper for recency of scholarly literature
        if verified and verified.get("status") == "non_paper":
            continue
        y = _year_of(ref, verified)
        if y is None:
            unknown_year += 1
            continue
        year_map[y] = year_map.get(y, 0) + 1

    dated = sum(year_map.values())
    recency: dict[str, Any] = {
        "status": "ok",
        "dated_count": dated,
        "unknown_year_count": unknown_year,
        "year_histogram": dict(sorted(year_map.items())),
        "windows": {},
    }
    for window in recent_windows:
        cutoff = as_of - window
        recent_n = sum(c for y, c in year_map.items() if y >= cutoff)
        recency["windows"][str(window)] = {
            "years": window,
            "cutoff_year_inclusive": cutoff,
            "recent_count": recent_n,
            "recent_ratio": (recent_n / dated) if dated else None,
        }
    out["recency"] = recency

    # Compact scores
    fab = out.get("fabrication") or {}
    cov = out.get("coverage") or {}
    out["scores"] = {
        "fabrication_rate": fab.get("fabrication_rate"),
        "coverage_recall": cov.get("recall"),
        "coverage_precision": cov.get("precision"),
        "recency_ratio_3y": (recency.get("windows") or {}).get("3", {}).get("recent_ratio"),
        "recency_ratio_5y": (recency.get("windows") or {}).get("5", {}).get("recent_ratio"),
    }
    return out
