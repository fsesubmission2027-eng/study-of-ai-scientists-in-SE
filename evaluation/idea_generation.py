"""Idea-generation quality scoring (Novelty / Feasibility / Clarity).

Novelty is judged against a task-level Solution Space built from the original
paper's mineru REFERENCES titles (+ related_work.json abstracts when matched).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from llm_client import chat_json
from framework_profile import get_framework_profile
from paths import find_idea
from solution_space import build_solution_space, format_solution_space_digest

DIMENSIONS = (
    "novelty",
    "feasibility",
    "clarity",
)

DIMENSION_RUBRICS: dict[str, dict[int, str]] = {
    "novelty": {
        1: (
            "Existing: the idea's core method is already clearly present or solved in the "
            "Solution Space; only tiny parameter / test-case changes."
        ),
        2: (
            "Trivial Mashup: a hard splice of existing technique A with technique B "
            "(e.g. swapping one module for an LLM) without deep mechanism innovation at "
            "the junction."
        ),
        3: (
            "Incremental: a meaningful extension or optimization of prior baseline work "
            "that fixes a concrete prior limitation, but the core paradigm is unchanged."
        ),
        4: (
            "Novel Combo / Cross-domain: spots a non-obvious link across areas and "
            "cleverly imports an existing method from another domain to address the "
            "current pain point, yielding a 1+1>2 effect."
        ),
        5: (
            "Paradigm Shift: proposes a new mechanism, architecture, or theory that does "
            "not exist in the Solution Space and overturns the prevailing solution approach."
        ),
    },
    "feasibility": {
        1: (
            "Theoretically infeasible / compute catastrophe: NP-hard-scale computation, "
            "must dynamically reproduce extremely complex system-level vulnerability "
            "environments, or depends on unavailable closed-source model internal weights; "
            "not doable by a single person."
        ),
        2: (
            "Extreme engineering barrier: requires building complex low-level tooling from "
            "scratch (custom compiler plugins, new vulnerability execution sandboxes), or "
            "an extremely heavy experimental pipeline with multi-month development."
        ),
        3: (
            "Moderate workload (sweet spot): needs nontrivial coding such as scripting "
            "existing open-source tools (parsers, CFG extractors) or building a custom "
            "graph-processing pipeline; standard research engineering effort."
        ),
        4: (
            "Low barrier / easy to implement: core logic can be quickly built on existing "
            "Python libraries or common ML frameworks; only small changes to a standard "
            "evaluation flow (e.g. prompt strategy tweaks or swapping metrics)."
        ),
        5: (
            "Extremely simple / near zero development: change a few parameters in existing "
            "code, or call an off-the-shelf library/API to validate; essentially out of the box."
        ),
    },
    "clarity": {
        1: (
            "Vague concept: full of empty buzzwords; problem undefined; method only gives "
            "a high-level direction with little substance."
        ),
        2: (
            "Broken logic: states a problem but the proposed solution does not match it, "
            "or never mentions experiments / evaluation."
        ),
        3: (
            "Complete frame but missing details: What/Why/How are present, yet key "
            "technical execution details or specific comparison plans are underspecified."
        ),
        4: (
            "Clear and concrete: steps are explicit with a reasonable, specific experiment "
            "design (baseline tools, metric definitions); can be turned into a solid proposal."
        ),
        5: (
            "Extremely clear and rigorous: system-architecture or pseudocode-level clarity; "
            "elaborates the plan in detail and also discusses limitations or "
            "defenses/mitigations."
        ),
    },
}

NOVELTY_CATEGORY = {
    1: "Existing",
    2: "Trivial Mashup",
    3: "Incremental",
    4: "Novel Combo / Cross-domain",
    5: "Paradigm Shift",
}


def _format_rubrics_for_prompt() -> str:
    lines: list[str] = []
    for name in DIMENSIONS:
        lines.append(f"### {name}")
        for score in range(1, 6):
            lines.append(f"  {score}: {DIMENSION_RUBRICS[name][score]}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _clamp_score_1_to_5(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score != score:
        return None
    return max(1.0, min(5.0, score))


def _json_to_idea_text(data: Any, *, max_chars: int = 18000) -> str:
    if isinstance(data, dict):
        # Prefer richer narrative fields when present.
        preferred_keys = (
            "Title",
            "title",
            "Name",
            "name",
            "Hypothesis",
            "hypothesis",
            "hypotheses_md",
            "Experiment",
            "experiment",
            "Method",
            "method",
            "Abstract",
            "abstract",
            "Interestingness",
            "Feasibility",
            "Novelty",
            "Motivation",
            "motivation",
            "Problem",
            "problem",
            "Contribution",
            "contribution",
            "selected_idea",
            "idea",
            "summary",
            "Executive Summary",
        )
        chunks: list[str] = []
        for key in preferred_keys:
            if key in data and data[key] not in (None, "", [], {}):
                val = data[key]
                if isinstance(val, (dict, list)):
                    chunks.append(f"## {key}\n{json.dumps(val, ensure_ascii=False, indent=2)}")
                else:
                    chunks.append(f"## {key}\n{val}")
        if not chunks:
            chunks.append(json.dumps(data, ensure_ascii=False, indent=2))
        text = "\n\n".join(chunks)
    elif isinstance(data, list):
        # AI-Scientist often stores a list of idea dicts; take the first / recommended.
        parts = []
        for i, item in enumerate(data[:3]):
            parts.append(f"# Idea candidate {i + 1}\n{_json_to_idea_text(item, max_chars=max_chars // 3)}")
        text = "\n\n".join(parts)
    else:
        text = str(data)
    return text[:max_chars]


def _extract_recommended_section(md: str) -> str:
    """If an IDEA_REPORT has a RECOMMENDED idea, prefer that block."""
    m = re.search(
        r"(?ims)^#{2,3}\s*.*RECOMMENDED.*$(.*?)(?=^#{2,3}\s|\Z)",
        md,
    )
    if m and len(m.group(0).strip()) > 200:
        # Include refined proposal if present after ranked ideas.
        refined = re.search(r"(?ims)^##\s*Refined Proposal\s*$.*", md)
        body = m.group(0).strip()
        if refined:
            body = body + "\n\n" + refined.group(0)[:8000]
        return body
    return md


def load_idea_text(path: Path, *, max_chars: int = 18000) -> str:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(raw)
            return _json_to_idea_text(data, max_chars=max_chars)
        except json.JSONDecodeError:
            return raw[:max_chars]
    if path.suffix.lower() in {".md", ".txt"}:
        return _extract_recommended_section(raw)[:max_chars]
    return raw[:max_chars]


def _task_context(task_dir: Path | None, *, max_chars: int = 4000) -> str:
    if task_dir is None:
        return ""
    task_md = task_dir / "task.md"
    if not task_md.is_file():
        return ""
    return task_md.read_text(encoding="utf-8", errors="replace")[:max_chars]


SYSTEM_PROMPT = """You are an expert research mentor scoring AI-generated research ideas.
Score ONLY the provided idea artifact (not the final paper).
Use the fixed 1-5 rubrics. Return ONLY valid JSON.
Novelty MUST be judged relative to the provided Solution Space (key innovations from
the original paper's references). Compare the idea's core method against those entries.
If the Solution Space is missing/empty, say so and score novelty more conservatively.
Feasibility judges engineering/compute/practicality burden (1=infeasible catastrophe,
5=near zero development). Clarity judges logical completeness and concreteness of the plan.
Do not reward vague ambition.
"""


def evaluate_idea_generation(
    run_dir: Path,
    *,
    task_dir: Path | None = None,
    idea_path: Path | None = None,
    model: str | None = None,
    skip_llm: bool = False,
    evals_root: Path | None = None,
    force_refresh_solution_space: bool = False,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    profile = get_framework_profile(run_dir)
    found = None
    path: Path | None = None
    if idea_path is not None:
        path = idea_path if idea_path.is_file() else None
    else:
        found = find_idea(run_dir, priority=profile.idea_priority)
        path = found.path if found else None

    base: dict[str, Any] = {
        "run_dir": str(run_dir),
        "task_dir": str(task_dir) if task_dir else None,
        "idea_path": str(path) if path else None,
        "status": "ok",
        "dimensions": {},
        "overall_score": None,
        "score_scale": "1-5",
        "dimension_order": list(DIMENSIONS),
        "solution_space": None,
        "notes": [
            "Scores the intermediate idea artifact (not the final paper).",
            "Dimensions: novelty, feasibility, clarity (each 1-5). Excitement removed.",
            "Novelty is scored against a Solution Space built from mineru REFERENCES "
            "titles (+ related_work.json abstracts when matched).",
        ],
    }
    if found is not None:
        base["idea_via"] = found.via
        base["idea_relative"] = found.relative

    if path is None:
        base["status"] = "missing_idea"
        base["hint"] = (
            "No idea artifact found under candidates like artifacts/idea.json, "
            "idea-stage/IDEA_REPORT.md, session/idea.json, tiny_idea.json, selected_idea.md."
        )
        return base

    if skip_llm:
        base["status"] = "idea_found_llm_skipped"
        base["idea_chars"] = path.stat().st_size
        return base

    idea_text = load_idea_text(path)
    if len(idea_text.strip()) < 40:
        base["status"] = "idea_too_short"
        base["hint"] = f"Idea file exists but content is too short: {path}"
        return base

    solution_digest = "(no Solution Space: task_dir missing or related_work unavailable)"
    if task_dir is not None:
        space = build_solution_space(
            task_dir,
            model=model,
            evals_root=evals_root,
            force=force_refresh_solution_space,
            skip_llm=False,
        )
        base["solution_space"] = {
            "status": space.get("status"),
            "paper_count": space.get("paper_count"),
            "entry_count": (
                len(space.get("entries") or [])
                if isinstance(space.get("entries"), list)
                else 0
            ),
            "cache_hit": space.get("cache_hit"),
            "source_file": space.get("source_file"),
            "stats": space.get("stats"),
            "error": space.get("error"),
        }
        if space.get("status") == "ok" and space.get("entries"):
            solution_digest = format_solution_space_digest(space)
        else:
            solution_digest = (
                f"(Solution Space unavailable: status={space.get('status')}; "
                f"{space.get('hint') or space.get('error') or 'no entries'})"
            )

    task_ctx = _task_context(task_dir)
    rubrics = _format_rubrics_for_prompt()
    user = f"""Score this AI-scientist research idea.

Score each dimension as an INTEGER 1-5 using the rubrics below.
Justification must quote concrete phrases from the idea text.

## Novelty special instructions
- Judge novelty ONLY relative to the Solution Space below.
- Map the idea to the closest Solution Space entries (cite their ids like R3, R12).
- Choose the rubric level that best matches:
  1 Existing / 2 Trivial Mashup / 3 Incremental / 4 Novel Combo / 5 Paradigm Shift
- For novelty, also return:
  - category: one of Existing | Trivial Mashup | Incremental | Novel Combo | Paradigm Shift
  - nearest_solution_space_ids: list of Solution Space ids that are closest
  - differentiation: what (if anything) is new vs those entries

## Rubrics
{rubrics}

Also provide:
- overall_score: float in [1, 5] (holistic; low feasibility should strongly pull overall down)
- summary: <= 120 words
- strengths: string array
- weaknesses: string array

Return JSON schema:
{{
  "novelty": {{
    "score": 1-5,
    "category": "Existing|Trivial Mashup|Incremental|Novel Combo|Paradigm Shift",
    "nearest_solution_space_ids": ["R1"],
    "differentiation": "...",
    "justification": "..."
  }},
  "feasibility": {{"score": 1-5, "justification": "..."}},
  "clarity": {{"score": 1-5, "justification": "..."}},
  "overall_score": 1-5,
  "summary": "...",
  "strengths": ["..."],
  "weaknesses": ["..."]
}}

=== TASK CONTEXT (optional) ===
{task_ctx or "(none)"}

=== SOLUTION SPACE ===
{solution_digest}

=== IDEA ARTIFACT ({path.name}) ===
{idea_text}
"""
    try:
        data = chat_json(system=SYSTEM_PROMPT, user=user, model=model, max_tokens=3000)
    except Exception as exc:  # noqa: BLE001
        base["status"] = "llm_failed"
        base["error"] = str(exc)
        return base

    dims: dict[str, Any] = {}
    scores: list[float] = []
    for name in DIMENSIONS:
        block = data.get(name) or {}
        if isinstance(block, dict):
            score = _clamp_score_1_to_5(block.get("score"))
        elif isinstance(block, (int, float)):
            score = _clamp_score_1_to_5(block)
            block = {"score": score, "justification": ""}
        else:
            score = None
            block = {}
        rubric_key = int(round(score)) if score is not None else None
        entry: dict[str, Any] = {
            "score": score,
            "justification": str(block.get("justification") or "")[:800],
            "rubric": DIMENSION_RUBRICS[name].get(rubric_key) if rubric_key else None,
        }
        if name == "novelty" and isinstance(block, dict):
            category = str(block.get("category") or "").strip()
            if not category and rubric_key in NOVELTY_CATEGORY:
                category = NOVELTY_CATEGORY[rubric_key]
            entry["category"] = category or None
            nearest = block.get("nearest_solution_space_ids")
            entry["nearest_solution_space_ids"] = (
                [str(x) for x in nearest[:12]] if isinstance(nearest, list) else []
            )
            entry["differentiation"] = str(block.get("differentiation") or "")[:800]
        dims[name] = entry
        if score is not None:
            scores.append(score)

    overall_f = _clamp_score_1_to_5(data.get("overall_score"))
    if overall_f is None and scores:
        overall_f = sum(scores) / len(scores)

    base.update(
        {
            "status": "ok",
            "dimensions": dims,
            "overall_score": overall_f,
            "summary": str(data.get("summary") or "")[:1000],
            "strengths": data.get("strengths") if isinstance(data.get("strengths"), list) else [],
            "weaknesses": data.get("weaknesses") if isinstance(data.get("weaknesses"), list) else [],
            "llm_meta": data.get("_meta"),
        }
    )
    return base
