#!/usr/bin/env python3
"""Evaluate an AI-scientist run on completeness, peer-review quality, and paper alignment.

Outputs (by default, sibling of ``ai_scientist_inputs``)::

  ~/ai_scientist_evals/<task>/<run>/evaluation.json
  ~/ai_scientist_evals/<task>/original_claims.json
  ~/ai_scientist_evals/<task>/solution_space.json
  ~/ai_scientist_evals/<task>/reference_verify_cache.json

Examples:
  python3 evaluation/run_evaluate.py \\
    --run-dir ~/ai_scientist_inputs/ASE-2025-003_.../workspace/aris_2026-07-23_08-36-08 \\
    --axes completeness

  python3 evaluation/run_evaluate.py \\
    --run-dir .../aris_... \\
    --task-dir .../ASE-2025-003_fuzzing_vulnerability_detection \\
    --axes literature_review \\
    --skip-verify   # optional: skip S2/arXiv existence checks
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

EVAL_ROOT = Path(__file__).resolve().parent
if str(EVAL_ROOT) not in sys.path:
    sys.path.insert(0, str(EVAL_ROOT))

from completeness import evaluate_completeness  # noqa: E402
from eval_layout import (  # noqa: E402
    default_evals_root,
    evaluation_json_path,
    original_claims_path,
    solution_space_path,
)
from experiment_analysis import evaluate_experiment_analysis  # noqa: E402
from fairness import build_fair_scores  # noqa: E402
from framework_profile import FAIRNESS_AUDIT, get_framework_profile  # noqa: E402
from idea_generation import evaluate_idea_generation  # noqa: E402
from literature_review import evaluate_literature_review  # noqa: E402
from paper_alignment import evaluate_paper_alignment  # noqa: E402
from peer_review import evaluate_peer_review  # noqa: E402


def infer_task_dir(run_dir: Path) -> Path | None:
    # .../task/workspace/<run> -> task
    if run_dir.parent.name == "workspace" and run_dir.parent.parent.is_dir():
        return run_dir.parent.parent
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate AI-scientist benchmark runs")
    parser.add_argument("--run-dir", required=True, help="Path to a single tool run directory")
    parser.add_argument(
        "--task-dir",
        default=None,
        help="Task directory containing mineru_sections.json (default: infer from run-dir)",
    )
    parser.add_argument(
        "--axes",
        default="all",
        help="Comma list: completeness,idea_generation,peer_review,alignment,literature_review,experiment_analysis,all",
    )
    parser.add_argument(
        "--idea-path",
        default=None,
        help="Override path to the idea artifact for idea_generation",
    )
    parser.add_argument(
        "--review-path",
        default=None,
        help="Downloaded Stanford APR / peer-review report path",
    )
    parser.add_argument(
        "--auto-paperreview",
        action="store_true",
        help="Submit PDF to paperreview.ai when no cached numerical_score; skip upload if score exists",
    )
    parser.add_argument(
        "--paperreview-email",
        default=None,
        help="Email for paperreview.ai (else PAPERREVIEW_EMAIL or benchmark_credentials.yaml)",
    )
    parser.add_argument(
        "--paperreview-venue",
        default="ICLR",
        help="Target venue for paperreview.ai (overall 1-10 score shown only for ICLR)",
    )
    parser.add_argument(
        "--paperreview-no-wait",
        action="store_true",
        help="Submit to paperreview.ai but do not block waiting for the review",
    )
    parser.add_argument(
        "--paperreview-resubmit",
        action="store_true",
        help="Force a new paperreview.ai submission even if stanford_apr.json already has a score",
    )
    parser.add_argument(
        "--paperreview-llm-fallback",
        action="store_true",
        help="If stanford_apr.json lacks numerical_score, infer 1-10 from review text via LLM",
    )
    parser.add_argument("--model", default=None, help="Override judge/extraction LLM model id")
    parser.add_argument(
        "--force-refresh-original",
        action="store_true",
        help="Re-extract original claims from mineru even if cache exists",
    )
    parser.add_argument(
        "--force-refresh-solution-space",
        action="store_true",
        help="Rebuild Solution Space from related_work.json even if cache exists",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip LLM calls (completeness still runs; others become stubs/status)",
    )
    parser.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip S2/arXiv reference existence checks in literature_review",
    )
    parser.add_argument(
        "--evals-root",
        default=None,
        help="Eval output root (default: sibling of ai_scientist_inputs → ~/ai_scientist_evals)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Override evaluation.json path (default: <evals-root>/<task>/<run>/evaluation.json)",
    )
    args = parser.parse_args()

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        print(f"run-dir not found: {run_dir}", file=sys.stderr)
        return 1

    task_dir = Path(args.task_dir).expanduser().resolve() if args.task_dir else infer_task_dir(run_dir)
    evals_root = (
        Path(args.evals_root).expanduser().resolve()
        if args.evals_root
        else default_evals_root()
    )
    axes_raw = [a.strip().lower() for a in args.axes.split(",") if a.strip()]
    if "all" in axes_raw:
        axes = [
            "completeness",
            "idea_generation",
            "experiment_analysis",
            "peer_review",
            "alignment",
            "literature_review",
        ]
    else:
        axes = axes_raw

    # ── Partial-run support ──────────────────────────────────────────────────
    # When only a subset of axes is requested, load the existing evaluation.json
    # (if any) and merge into it so previously evaluated axes are preserved.
    out_path_preview = (
        Path(args.out).expanduser().resolve()
        if args.out
        else evaluation_json_path(run_dir, task_dir=task_dir, evals_root=evals_root)
    )
    existing_report: dict = {}
    if out_path_preview.exists() and "all" not in axes_raw:
        try:
            existing_report = json.loads(out_path_preview.read_text(encoding="utf-8"))
            print(f"[eval] merging into existing {out_path_preview}")
        except Exception as exc:  # noqa: BLE001
            print(f"[eval] could not load existing evaluation.json, starting fresh: {exc}", file=sys.stderr)

    report: dict = {
        # Preserve top-level metadata from existing report if available.
        **{k: existing_report[k] for k in ("run_dir", "task_dir", "framework", "fairness_audit") if k in existing_report},
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "run_dir": str(run_dir),
        "task_dir": str(task_dir) if task_dir else None,
        "framework": get_framework_profile(run_dir).key,
        "fairness_audit": FAIRNESS_AUDIT,
        # Carry forward axes from previous run; extend with newly requested axes.
        "axes": sorted(set(existing_report.get("axes", [])) | set(axes)),
        # Seed results with previously evaluated axes so they survive the rewrite.
        "results": dict(existing_report.get("results", {})),
    }

    if "completeness" in axes:
        print("[eval] completeness...")
        try:
            report["results"]["completeness"] = evaluate_completeness(run_dir, task_dir=task_dir)
            c = report["results"]["completeness"]
            print(
                f"  complete={c['complete']} required={c['required_score']} "
                f"bonus={c['bonus_score']} missing={c['missing']}"
            )
        except Exception as exc:  # noqa: BLE001
            report["results"]["completeness"] = {"status": "error", "error": str(exc)}
            print(f"  ERROR: {exc}", file=sys.stderr)

    if "idea_generation" in axes:
        print("[eval] idea_generation...")
        try:
            idea_path = Path(args.idea_path).expanduser().resolve() if args.idea_path else None
            report["results"]["idea_generation"] = evaluate_idea_generation(
                run_dir,
                task_dir=task_dir,
                idea_path=idea_path,
                model=args.model,
                skip_llm=args.skip_llm,
                evals_root=evals_root,
                force_refresh_solution_space=args.force_refresh_solution_space,
            )
            ig = report["results"]["idea_generation"]
            nov = (ig.get("dimensions") or {}).get("novelty") or {}
            print(
                f"  status={ig.get('status')} overall={ig.get('overall_score')} "
                f"novelty={nov.get('score')}({nov.get('category')}) "
                f"path={ig.get('idea_relative') or ig.get('idea_path')}"
            )
        except Exception as exc:  # noqa: BLE001
            report["results"]["idea_generation"] = {"status": "error", "error": str(exc)}
            print(f"  ERROR: {exc}", file=sys.stderr)

    if "peer_review" in axes:
        print("[eval] peer_review...")
        try:
            review_path = Path(args.review_path).expanduser().resolve() if args.review_path else None
            report["results"]["peer_review"] = evaluate_peer_review(
                run_dir,
                review_path=review_path,
                model=args.model,
                skip_llm=args.skip_llm,
                auto_paperreview=args.auto_paperreview,
                paperreview_email=args.paperreview_email,
                paperreview_venue=args.paperreview_venue,
                paperreview_wait=not args.paperreview_no_wait,
                paperreview_resubmit=args.paperreview_resubmit,
                paperreview_llm_fallback=args.paperreview_llm_fallback,
            )
            pr = report["results"]["peer_review"]
            print(
                f"  status={pr.get('status')} overall={pr.get('overall_score')} "
                f"scale={pr.get('score_scale')} method={pr.get('scoring_method')}"
            )
        except Exception as exc:  # noqa: BLE001
            report["results"]["peer_review"] = {"status": "error", "error": str(exc)}
            print(f"  ERROR: {exc}", file=sys.stderr)

    if "alignment" in axes:
        print("[eval] alignment...")
        try:
            if task_dir is None:
                report["results"]["alignment"] = {
                    "status": "missing_task_dir",
                    "hint": "Pass --task-dir pointing at the task root with mineru_sections.json",
                }
                print("  status=missing_task_dir")
            else:
                report["results"]["alignment"] = evaluate_paper_alignment(
                    run_dir,
                    task_dir,
                    model=args.model,
                    force_refresh_original=args.force_refresh_original,
                    skip_llm=args.skip_llm,
                    evals_root=evals_root,
                )
                al = report["results"]["alignment"]
                print(
                    f"  status={al.get('status')} direction={al.get('direction_consistency')} "
                    f"score={al.get('overall_alignment_score')}"
                )
        except Exception as exc:  # noqa: BLE001
            report["results"]["alignment"] = {"status": "error", "error": str(exc)}
            print(f"  ERROR: {exc}", file=sys.stderr)

    if "experiment_analysis" in axes:
        print("[eval] experiment_analysis...")
        try:
            report["results"]["experiment_analysis"] = evaluate_experiment_analysis(
                run_dir,
                task_dir,
                model=args.model,
                skip_llm=args.skip_llm,
            )
            ea = report["results"]["experiment_analysis"]
            sc = ea.get("scores") or {}
            print(
                f"  success={sc.get('experiment_success')} "
                f"idea_code={sc.get('idea_code_score')} "
                f"setup_cov={sc.get('setup_coverage')} "
                f"ablation={sc.get('ablation_coverage_score')} "
                f"sig_ok={sc.get('overall_significance_ok')} "
                f"results_paper={sc.get('results_paper_score')} "
                f"hiding={sc.get('hiding_unfavorable_suspected')}"
            )
        except Exception as exc:  # noqa: BLE001
            report["results"]["experiment_analysis"] = {"status": "error", "error": str(exc)}
            print(f"  ERROR: {exc}", file=sys.stderr)

    if "literature_review" in axes:
        print("[eval] literature_review...")
        try:
            report["results"]["literature_review"] = evaluate_literature_review(
                run_dir,
                task_dir,
                evals_root=evals_root,
                skip_verify=args.skip_verify,
            )
            lit = report["results"]["literature_review"]
            fab = (lit.get("fabrication") or {})
            cov = (lit.get("coverage") or {})
            rec = (lit.get("recency") or {})
            print(
                f"  status={lit.get('status')} refs={lit.get('agent_ref_count')} "
                f"fake_rate={fab.get('fabrication_rate')} "
                f"recall={cov.get('recall')} "
                f"recency3y={(rec.get('windows') or {}).get('3', {}).get('recent_ratio')}"
            )
        except Exception as exc:  # noqa: BLE001
            report["results"]["literature_review"] = {"status": "error", "error": str(exc)}
            print(f"  ERROR: {exc}", file=sys.stderr)

    # Compact top-level scores for dashboards.
    scores = {}
    comp = report["results"].get("completeness") or {}
    if comp:
        scores["completeness"] = {
            "complete": comp.get("complete"),
            "overall_score": comp.get("overall_score"),
            "required_score": comp.get("required_score"),
            "bonus_score": comp.get("bonus_score"),
        }
    pr = report["results"].get("peer_review") or {}
    if pr:
        scores["peer_review"] = {
            "status": pr.get("status"),
            "optional": pr.get("optional", pr.get("status") == "not_provided"),
            "overall_score": pr.get("overall_score"),
            "score_scale": pr.get("score_scale"),
            "scoring_method": pr.get("scoring_method"),
        }
    ig = report["results"].get("idea_generation") or {}
    if ig:
        nov = (ig.get("dimensions") or {}).get("novelty") or {}
        scores["idea_generation"] = {
            "status": ig.get("status"),
            "overall_score": ig.get("overall_score"),
            "dimensions": {
                name: (ig.get("dimensions") or {}).get(name, {}).get("score")
                for name in ("novelty", "feasibility", "clarity")
            },
            "novelty_category": nov.get("category"),
            "solution_space_status": (ig.get("solution_space") or {}).get("status"),
        }
    al = report["results"].get("alignment") or {}
    if al:
        scores["alignment"] = {
            "status": al.get("status"),
            "direction_consistency": al.get("direction_consistency"),
            "overall_alignment_score": al.get("overall_alignment_score"),
        }
    lit = report["results"].get("literature_review") or {}
    if lit:
        scores["literature_review"] = lit.get("scores") or {
            "fabrication_rate": (lit.get("fabrication") or {}).get("fabrication_rate"),
            "coverage_recall": (lit.get("coverage") or {}).get("recall"),
            "recency_ratio_3y": ((lit.get("recency") or {}).get("windows") or {})
            .get("3", {})
            .get("recent_ratio"),
            "recency_ratio_5y": ((lit.get("recency") or {}).get("windows") or {})
            .get("5", {})
            .get("recent_ratio"),
        }
    ea = report["results"].get("experiment_analysis") or {}
    if ea:
        scores["experiment_analysis"] = ea.get("scores") or {}
    report["scores"] = scores
    report["fair_scores"] = build_fair_scores(report["results"])
    report["evals_root"] = str(evals_root)
    if task_dir is not None:
        report["claims_cache"] = str(original_claims_path(task_dir, evals_root=evals_root))
        report["solution_space_cache"] = str(
            solution_space_path(task_dir, evals_root=evals_root)
        )

    out_path = out_path_preview
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[eval] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
