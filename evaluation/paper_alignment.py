"""Compare agent paper/results against original paper claims & SOTA from MinerU."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from llm_client import chat_json
from mineru_digest import (
    format_mineru_digest,
    load_mineru,
    mineru_selection_stats,
    select_mineru_blocks,
)
from paths import find_paper_document
from results_normalize import normalize_results


EXTRACT_SYSTEM = """You extract scientific claims and reported metrics from a paper.
Return ONLY valid JSON. Do not invent numbers that are not in the text.
If a metric value is unclear, omit it or set value to null and mark confidence low.
"""

COMPARE_SYSTEM = """You compare an AI-scientist run against the original paper's claims/metrics.
Be conservative: mark incomparable when protocols differ or evidence is missing.
Do not punish same-direction reduced-scale experiments with a zero alignment score.
Return ONLY valid JSON.
direction_consistency must be exactly one of: consistent, mixed, conflicting, unknown, same_direction_incomparable.
Do not echo the list. score_rationale must be a real sentence, not a placeholder.
"""

_ALIGNMENT_DIRECTIONS = {
    "consistent",
    "mixed",
    "conflicting",
    "unknown",
    "same_direction_incomparable",
}
_PLACEHOLDER_RATIONALES = {
    "short reason for the score band chosen",
    "short reason",
    "one sentence on which claims agree or conflict",
    "...",
}


def extraction_has_substance(data: dict[str, Any]) -> bool:
    claims = data.get("claims") if isinstance(data.get("claims"), list) else []
    metrics = data.get("metrics") if isinstance(data.get("metrics"), list) else []
    conclusion = str(data.get("overall_conclusion") or "").strip()
    return bool(claims or metrics or len(conclusion) >= 40)


def extraction_error(data: dict[str, Any]) -> str | None:
    if extraction_has_substance(data):
        return None
    return "claims, metrics, and overall_conclusion are empty"


def alignment_summary_error(data: dict[str, Any]) -> str | None:
    summary = data.get("summary")
    if not isinstance(summary, dict) or not summary:
        return "summary is empty"
    try:
        score = float(summary.get("overall_alignment_score"))
    except (TypeError, ValueError):
        return "overall_alignment_score is not a number"
    if not 0.0 <= score <= 1.0:
        return "overall_alignment_score is outside [0, 1]"
    direction = str(summary.get("direction_consistency") or "").strip().lower()
    if direction not in _ALIGNMENT_DIRECTIONS:
        return "direction_consistency must be one label, not the schema list"
    rationale = str(summary.get("score_rationale") or "").strip()
    if rationale.lower() in _PLACEHOLDER_RATIONALES or len(rationale) < 12:
        return "score_rationale is a placeholder"
    if not isinstance(data.get("claim_alignment"), list):
        return "claim_alignment must be a list"
    return None


def _postprocess_alignment_summary(
    summary: dict[str, Any],
    claim_alignment: list[Any],
    agent: dict[str, Any],
) -> dict[str, Any]:
    """Safety net: all-incomparable + near-zero score → mid-low same-direction band."""
    out = dict(summary or {})
    labels = [
        str(c.get("label") or "").lower()
        for c in claim_alignment
        if isinstance(c, dict)
    ]
    if not labels:
        return out

    all_incomparable = all(lb == "incomparable" for lb in labels)
    try:
        score = float(out.get("overall_alignment_score"))
    except (TypeError, ValueError):
        score = None

    agent_has_substance = bool(agent.get("claims") or agent.get("metrics") or agent.get("overall_conclusion"))
    if all_incomparable and agent_has_substance and (score is None or score <= 0.05):
        out["overall_alignment_score"] = 0.4
        dc = str(out.get("direction_consistency") or "").strip().lower()
        if dc in {"", "unknown"}:
            out["direction_consistency"] = "same_direction_incomparable"
        note = (
            "Postprocessed: all claims incomparable with near-zero score; "
            "raised to 0.4 (same-direction protocol/scale mismatch floor)."
        )
        prev = str(out.get("score_rationale") or "").strip()
        out["score_rationale"] = (prev + " | " + note).strip(" |") if prev else note
        out["score_postprocessed"] = True
    return out


def _compact_metrics(metrics_obj: Any, *, max_chars: int = 6000) -> Any:
    """Shrink nested metrics trees for LLM prompts while keeping numeric leaves."""
    if metrics_obj is None:
        return None
    text = json.dumps(metrics_obj, ensure_ascii=False)
    if len(text) <= max_chars:
        return metrics_obj

    def shrink(node: Any, depth: int = 0) -> Any:
        if isinstance(node, dict):
            # Prefer keeping numeric / short fields.
            keep: dict[str, Any] = {}
            for key, value in node.items():
                key_l = str(key).lower()
                if isinstance(value, (int, float, bool)) or value is None:
                    keep[key] = value
                elif isinstance(value, str) and len(value) < 120:
                    keep[key] = value
                elif any(
                    token in key_l
                    for token in (
                        "success",
                        "ratio",
                        "mean",
                        "time",
                        "auroc",
                        "f1",
                        "acc",
                        "score",
                        "metric",
                        "baseline",
                        "sota",
                        "ci",
                        "confidence",
                    )
                ):
                    keep[key] = shrink(value, depth + 1)
                elif depth < 3 and isinstance(value, (dict, list)):
                    keep[key] = shrink(value, depth + 1)
            return keep
        if isinstance(node, list):
            return [shrink(x, depth + 1) for x in node[:20]]
        return node

    compact = shrink(metrics_obj)
    text2 = json.dumps(compact, ensure_ascii=False)
    if len(text2) > max_chars:
        return text2[:max_chars]
    return compact


def _agent_side_bundle(run_dir: Path, *, max_tex_chars: int = 8000) -> dict[str, Any]:
    paper = find_paper_document(run_dir)
    norm = normalize_results(run_dir)
    metrics_obj = norm.data if norm.status == "ok" else None
    metrics_path = norm.relative if norm.status == "ok" else None

    paper_text = ""
    paper_rel = None
    paper_kind = None
    if paper is not None:
        paper_text = paper.path.read_text(encoding="utf-8", errors="replace")[:max_tex_chars]
        paper_rel = paper.relative
        paper_kind = paper.category

    return {
        "paper_tex_path": paper_rel,
        "paper_tex_excerpt": paper_text,
        "paper_kind": paper_kind,
        "metrics_path": metrics_path,
        "metrics": _compact_metrics(metrics_obj),
    }


def extract_claims_from_mineru(
    task_dir: Path,
    *,
    model: str | None = None,
    cache_path: Path | None = None,
    force: bool = False,
    evals_root: Path | None = None,
) -> dict[str, Any]:
    task_dir = task_dir.resolve()
    if cache_path is None:
        from eval_layout import original_claims_path

        cache_path = original_claims_path(task_dir, evals_root=evals_root)
    if cache_path.is_file() and not force:
        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            # Empty caches were written when reasoning consumed the whole token budget.
            if (
                isinstance(cached, dict)
                and cached.get("status") in (None, "ok")
                and extraction_has_substance(cached)
            ):
                cached["cache_hit"] = True
                return cached
        except (OSError, json.JSONDecodeError):
            pass

    mineru = load_mineru(task_dir)
    if mineru is None:
        return {
            "status": "missing_mineru_sections",
            "task_dir": str(task_dir),
            "hint": f"Expected {task_dir / 'mineru_sections.json'}",
        }

    blocks = select_mineru_blocks(mineru)
    digest = format_mineru_digest(blocks)
    stats = mineru_selection_stats(blocks)

    user = f"""Extract the original paper's main claims and key reported metrics/SOTA numbers.

Paper title: {mineru.get('title') or mineru.get('task_title') or ''}
Task id: {mineru.get('task_id') or task_dir.name}

IMPORTANT about the digest:
- MinerU section keys are often WRONG (many experiment/result subsections are labeled "other").
- Trust section TITLES and the inferred role in each heading, not the raw mineru key.
- Headings look like: ### [<inferred_role>] <title> (source=...; mineru_key=...; via=...)
- The digest is non-empty. Return at least one claim or one metric. An empty object is invalid.

Return JSON:
{{
  "claims": [
    {{
      "id": "C1",
      "statement": "...",
      "direction": "improves|degrades|no_difference|mixed|neutral|unknown",
      "metric_names": ["..."],
      "evidence_quote": "short quote",
      "confidence": 0.0-1.0
    }}
  ],
  "metrics": [
    {{
      "name": "success_ratio|auroc|accuracy|...",
      "value": 0.0,
      "unit": "%|ratio|seconds|null",
      "higher_is_better": true,
      "setting": "dataset/model/condition briefly",
      "is_sota_or_best": true,
      "baseline_name": "optional",
      "baseline_value": null,
      "evidence_quote": "short quote",
      "confidence": 0.0-1.0
    }}
  ],
  "overall_conclusion": "1-3 sentences",
  "comparable_notes": "what experimental protocol details matter for fair comparison"
}}

=== ORIGINAL PAPER DIGEST ===
{digest}
"""
    try:
        data = chat_json(
            system=EXTRACT_SYSTEM,
            user=user,
            model=model,
            max_tokens=3500,
            validate=extraction_error,
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "empty_or_invalid_extraction",
            "task_dir": str(task_dir),
            "paper_title": mineru.get("title"),
            "error": str(exc),
        }
    out = {
        "status": "ok",
        "task_dir": str(task_dir),
        "paper_title": mineru.get("title"),
        "task_id": mineru.get("task_id"),
        "selection": stats,
        "claims": data.get("claims") if isinstance(data.get("claims"), list) else [],
        "metrics": data.get("metrics") if isinstance(data.get("metrics"), list) else [],
        "overall_conclusion": data.get("overall_conclusion"),
        "comparable_notes": data.get("comparable_notes"),
        "llm_meta": data.get("_meta"),
        "cache_hit": False,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def extract_claims_from_agent(
    run_dir: Path,
    *,
    model: str | None = None,
) -> dict[str, Any]:
    bundle = _agent_side_bundle(run_dir)
    if not bundle["paper_tex_excerpt"] and bundle["metrics"] is None:
        return {
            "status": "missing_agent_paper_or_metrics",
            "run_dir": str(run_dir),
        }

    user = f"""Extract the AI-scientist paper's claims and reported metrics.

Return JSON with the same schema:
{{
  "claims": [{{"id":"A1","statement":"...","direction":"improves|degrades|no_difference|mixed|neutral|unknown","metric_names":[],"evidence_quote":"...","confidence":0.0}}],
  "metrics": [{{"name":"...","value":0.0,"unit":null,"higher_is_better":true,"setting":"...","is_sota_or_best":false,"baseline_name":null,"baseline_value":null,"evidence_quote":"...","confidence":0.0}}],
  "overall_conclusion": "..."
}}

Prefer numbers from metrics JSON when present; use the paper for qualitative claims.
Return at least one claim or one metric. An empty object is invalid.

=== METRICS JSON PATH: {bundle['metrics_path']} ===
{json.dumps(bundle['metrics'], ensure_ascii=False, indent=2)[:8000] if bundle['metrics'] is not None else '(none)'}

=== PAPER TEX EXCERPT PATH: {bundle['paper_tex_path']} ===
{bundle['paper_tex_excerpt'] or '(none)'}
"""
    data = chat_json(
        system=EXTRACT_SYSTEM,
        user=user,
        model=model,
        max_tokens=5000,
        validate=extraction_error,
    )
    return {
        "status": "ok",
        "run_dir": str(run_dir),
        "claims": data.get("claims") if isinstance(data.get("claims"), list) else [],
        "metrics": data.get("metrics") if isinstance(data.get("metrics"), list) else [],
        "overall_conclusion": data.get("overall_conclusion"),
        "sources": {
            "metrics_path": bundle["metrics_path"],
            "paper_tex_path": bundle["paper_tex_path"],
        },
        "llm_meta": data.get("_meta"),
    }


def compare_alignment(
    original: dict[str, Any],
    agent: dict[str, Any],
    *,
    model: str | None = None,
) -> dict[str, Any]:
    user = f"""Compare ORIGINAL paper extractions vs AGENT run extractions.

Decide for each original claim whether the agent is:
- consistent (same direction)
- conflicting (opposite direction)
- partial
- missing (agent did not address)
- incomparable (different task/protocol)

For metrics, only compute deltas when comparable=true.
If the agent used a reduced protocol, mark incomparable rather than inventing SOTA wins.

Scoring rules for summary.overall_alignment_score in [0,1]:
- Mainly claim-direction agreement when claims are comparable.
- Do NOT give 0.0 merely because protocol/scale/tool-name differs.
- If ALL original claims are labeled incomparable BUT the agent clearly works on the
  same research problem/direction (e.g. same task family, same kind of metric goal),
  set overall_alignment_score to a mid-low value in [0.30, 0.55] and
  direction_consistency to "same_direction_incomparable" (or "mixed").
- Use overall_alignment_score near 0.0 ONLY when the agent addresses a different
  problem entirely, or when comparable claims clearly conflict.
- direction_consistency must be exactly one of: consistent, mixed, conflicting, unknown, same_direction_incomparable.
- Do not copy the example score or rationale unless they are actually correct.

Return JSON:
{{
  "claim_alignment": [
    {{
      "original_claim_id": "C1",
      "agent_claim_id": "A1 or null",
      "label": "consistent|conflicting|partial|missing|incomparable",
      "rationale": "..."
    }}
  ],
  "metric_alignment": [
    {{
      "original_metric": "name",
      "agent_metric": "name or null",
      "comparable": false,
      "original_value": null,
      "agent_value": null,
      "delta_abs": null,
      "delta_rel": null,
      "direction_vs_original_sota": "better|worse|equal|unknown|incomparable",
      "rationale": "..."
    }}
  ],
  "summary": {{
    "direction_consistency": "mixed",
    "consistent_claim_ratio": 0.0,
    "has_comparable_metrics": false,
    "sota_improvement_summary": "text or N/A",
    "overall_alignment_score": 0.5,
    "score_rationale": "one sentence on which claims agree or conflict"
  }},
  "warnings": ["..."]
}}

=== ORIGINAL ===
{json.dumps({k: original.get(k) for k in ('paper_title','overall_conclusion','claims','metrics','comparable_notes')}, ensure_ascii=False, indent=2)[:12000]}

=== AGENT ===
{json.dumps({k: agent.get(k) for k in ('overall_conclusion','claims','metrics','sources')}, ensure_ascii=False, indent=2)[:12000]}
"""
    data = chat_json(
        system=COMPARE_SYSTEM,
        user=user,
        model=model,
        max_tokens=3500,
        validate=alignment_summary_error,
    )
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    claim_alignment = data.get("claim_alignment") if isinstance(data.get("claim_alignment"), list) else []
    metric_alignment = data.get("metric_alignment") if isinstance(data.get("metric_alignment"), list) else []
    summary = _postprocess_alignment_summary(summary, claim_alignment, agent)
    return {
        "status": "ok",
        "claim_alignment": claim_alignment,
        "metric_alignment": metric_alignment,
        "summary": summary,
        "warnings": data.get("warnings") if isinstance(data.get("warnings"), list) else [],
        "llm_meta": data.get("_meta"),
    }


def evaluate_paper_alignment(
    run_dir: Path,
    task_dir: Path,
    *,
    model: str | None = None,
    force_refresh_original: bool = False,
    skip_llm: bool = False,
    evals_root: Path | None = None,
    claims_cache_path: Path | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    task_dir = task_dir.resolve()
    out: dict[str, Any] = {
        "run_dir": str(run_dir),
        "task_dir": str(task_dir),
        "status": "ok",
    }
    if skip_llm:
        mineru = load_mineru(task_dir)
        blocks = select_mineru_blocks(mineru) if mineru else []
        out.update(
            {
                "status": "llm_skipped",
                "mineru_present": mineru is not None,
                "selection": mineru_selection_stats(blocks) if blocks else None,
            }
        )
        return out

    original = extract_claims_from_mineru(
        task_dir,
        model=model,
        force=force_refresh_original,
        cache_path=claims_cache_path,
        evals_root=evals_root,
    )
    if original.get("status") != "ok":
        out["status"] = original.get("status") or "original_extract_failed"
        out["original"] = original
        return out

    try:
        agent = extract_claims_from_agent(run_dir, model=model)
    except Exception as exc:  # noqa: BLE001
        out["status"] = "agent_extract_failed"
        out["original"] = {
            "paper_title": original.get("paper_title"),
            "claims": original.get("claims"),
            "metrics": original.get("metrics"),
            "overall_conclusion": original.get("overall_conclusion"),
            "cache_hit": original.get("cache_hit"),
        }
        out["error"] = str(exc)
        return out

    if agent.get("status") != "ok":
        out["status"] = agent.get("status") or "agent_extract_failed"
        out["original"] = original
        out["agent"] = agent
        return out

    try:
        comparison = compare_alignment(original, agent, model=model)
    except Exception as exc:  # noqa: BLE001
        out["status"] = "compare_failed"
        out["original"] = original
        out["agent"] = agent
        out["error"] = str(exc)
        return out
    out.update(
        {
            "original": {
                "paper_title": original.get("paper_title"),
                "selection": original.get("selection"),
                "claims": original.get("claims"),
                "metrics": original.get("metrics"),
                "overall_conclusion": original.get("overall_conclusion"),
                "comparable_notes": original.get("comparable_notes"),
                "cache_hit": original.get("cache_hit"),
            },
            "agent": agent,
            "comparison": comparison,
            "overall_alignment_score": (comparison.get("summary") or {}).get("overall_alignment_score"),
            "direction_consistency": (comparison.get("summary") or {}).get("direction_consistency"),
        }
    )
    return out
