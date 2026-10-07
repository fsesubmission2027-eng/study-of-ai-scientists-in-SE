"""Experiment + analysis evaluation (success, idea↔code, setup coverage, ablation, results↔paper).

Axes covered:
  1. experiment_success — did a real experiment finish with numeric results?
  2. idea_code_consistency — LLM graded alignment of idea vs experiment code
  3. setup_coverage — baselines / metrics / datasets vs task.md gold + weak-protocol flags
  4. ablation_significance — LLM extracts method components; checks ablation + significance
  6. results_paper_consistency — final metrics vs paper (LLM direct comparison)
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from idea_generation import load_idea_text
from llm_client import chat_json
from paths import (
    _load_manifest,
    find_code,
    find_idea,
    find_paper_document,
    find_results,
)
from results_normalize import (
    is_stub_metrics,
    normalize_results,
    serialize_final_results_for_llm,
    walk_numeric_leaves,
)

# ---------------------------------------------------------------------------
# Rubrics for idea↔code consistency (1–5)
# ---------------------------------------------------------------------------

IDEA_CODE_RUBRICS: dict[int, str] = {
    1: (
        "Severe mismatch: code implements a different problem/method than the idea, "
        "or is unrelated boilerplate."
    ),
    2: (
        "Weak alignment: only superficial overlap; core hypothesis, method, or evaluation "
        "in the idea is missing or replaced."
    ),
    3: (
        "Partial alignment: main direction matches, but important components from the idea "
        "(baselines, metrics, protocol, subjects) are dropped or altered without clear mapping."
    ),
    4: (
        "Strong alignment: code largely implements the idea's method and evaluation; only "
        "minor omissions or declared simplifications."
    ),
    5: (
        "Excellent alignment: experiment entrypoints, metrics, and protocol clearly realize "
        "the stated idea (including scoped reductions that match the idea text)."
    ),
}

RESULTS_PAPER_RUBRICS: dict[int, str] = {
    1: (
        "Severe inconsistency or concealment: paper claims contradict metrics, invent "
        "numbers, or omit clear failures/negative findings that dominate the results."
    ),
    2: (
        "Poor consistency: several key numbers/claims disagree with metrics, or major "
        "unfavorable outcomes are missing from the narrative."
    ),
    3: (
        "Mixed: overall story roughly matches, but some claims are overstated or some "
        "negative cells are under-discussed."
    ),
    4: (
        "Mostly consistent: reported conclusions track the metrics; negative/failed "
        "settings are acknowledged with only minor gaps."
    ),
    5: (
        "Highly consistent and transparent: numbers and conclusions match metrics; "
        "failures and limitations are fairly reported."
    ),
}


def _clamp_1_to_5(value: Any) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if score != score:
        return None
    return max(1.0, min(5.0, score))


def _norm_name(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("dev-urandom", "urandom").replace("/dev/urandom", "urandom")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def _walk_numeric_leaves(obj: Any, *, path: str = "") -> list[tuple[str, float]]:
    return walk_numeric_leaves(obj, path=path)


def _is_stub_metrics(data: Any) -> bool:
    return is_stub_metrics(data)


def _primary_metrics_artifact(run_dir: Path) -> tuple[Path | None, Any | None, str]:
    norm = normalize_results(run_dir)
    if norm.status != "ok":
        return None, None, ""
    return norm.path, norm.data, norm.relative


# ---------------------------------------------------------------------------
# 1) Experiment success
# ---------------------------------------------------------------------------

def assess_experiment_success(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    manifest = _load_manifest(run_dir)
    norm = normalize_results(run_dir)
    path, data, rel = norm.path, norm.data, norm.relative
    leaves = _walk_numeric_leaves(data) if data is not None else []
    numeric_count = len(leaves)

    status_bits = {
        "has_results_file": path is not None,
        "non_stub": data is not None and not _is_stub_metrics(data),
        "numeric_leaf_count": numeric_count,
        "min_numeric_ok": numeric_count >= 3,
    }

    # Manifest hints (soft)
    m_status = str(manifest.get("status") or "").lower()
    returncode = manifest.get("returncode")
    benchmark_complete = manifest.get("benchmark_complete")
    artifacts = manifest.get("artifacts") if isinstance(manifest.get("artifacts"), dict) else {}
    manifest_metrics = artifacts.get("metrics") is True or artifacts.get("results") is True

    success = bool(status_bits["non_stub"] and status_bits["min_numeric_ok"])
    # Soft downgrade signals
    warnings: list[str] = []
    if returncode not in (None, 0, "0"):
        warnings.append(f"manifest.returncode={returncode}")
    if benchmark_complete is False:
        warnings.append("manifest.benchmark_complete=false")
    if m_status in {"failed", "error", "crashed"}:
        warnings.append(f"manifest.status={m_status}")

    # Suspicious numeric values (e.g. negative time)
    suspicious = []
    for p, v in leaves[:500]:
        pl = p.lower()
        if "time" in pl and v < 0:
            suspicious.append({"path": p, "value": v, "reason": "negative_time"})
        if "success_ratio" in pl and (v < 0 or v > 1.0001):
            suspicious.append({"path": p, "value": v, "reason": "success_ratio_out_of_range"})
    if len(suspicious) > 20:
        suspicious = suspicious[:20]

    return {
        "status": "ok" if success else "failed_or_incomplete",
        "success": success,
        "metrics_path": rel or None,
        "absolute_metrics_path": str(path) if path else None,
        "checks": status_bits,
        "manifest_hints": {
            "status": manifest.get("status"),
            "returncode": returncode,
            "benchmark_complete": benchmark_complete,
            "artifacts_metrics_flag": manifest_metrics,
        },
        "warnings": warnings,
        "suspicious_values": suspicious,
        "note": (
            "success=true requires substantive results (framework-aware path) with >=3 numeric leaves. "
            "Supports metrics.json, results.json, experiment_results.txt, etc. "
            "Manifest returncode/benchmark_complete are soft warnings only."
        ),
    }


# ---------------------------------------------------------------------------
# 3) Setup coverage (baselines / metrics / datasets)
# ---------------------------------------------------------------------------

def _parse_task_setup(task_dir: Path) -> dict[str, Any]:
    """Parse Datasets / Baselines / Metrics blocks from task.md (and metadata.json)."""
    out: dict[str, Any] = {
        "datasets": [],
        "baselines": [],
        "metrics": [],
        "protocol": {},
        "sources": [],
    }
    task_md = task_dir / "task.md"
    if task_md.is_file():
        out["sources"].append(str(task_md))
        text = task_md.read_text(encoding="utf-8", errors="replace")

        def _block(header: str) -> str:
            m = re.search(
                rf"(?ims)^###\s*{header}\s*$.*?```(.*?)```",
                text,
            )
            return m.group(1) if m else ""

        for name in re.findall(r"(?im)^-\s*name:\s*(.+)$", _block("Datasets")):
            out["datasets"].append(name.strip())
        for name in re.findall(r"(?im)^-\s*name:\s*(.+)$", _block("Baselines")):
            out["baselines"].append(name.strip())
        for name in re.findall(r"(?im)^-\s*name:\s*(.+)$", _block("Metrics")):
            out["metrics"].append(name.strip())

        # Protocol cues from Constraints
        cons = re.search(r"(?ims)^###\s*Constraints\s*$(.*?)(?=^##\s|\Z)", text)
        if cons:
            ctext = cons.group(1)
            tm = re.search(r"(\d+)\s*[- ]*hour", ctext, flags=re.I)
            if tm:
                out["protocol"]["timeout_hours"] = int(tm.group(1))
            rm = re.search(r"repeated\s+(\d+)\s+times", ctext, flags=re.I)
            if rm:
                out["protocol"]["trials"] = int(rm.group(1))

    meta = task_dir / "metadata.json"
    if meta.is_file():
        data = _load_json(meta)
        if isinstance(data, dict):
            out["sources"].append(str(meta))
            setup = data.get("experiment_setup") or data.get("Experiment Setup") or {}
            if isinstance(setup, dict):
                for key, bucket in (
                    ("datasets", "datasets"),
                    ("baselines", "baselines"),
                    ("metrics", "metrics"),
                ):
                    items = setup.get(key) or setup.get(key.capitalize()) or []
                    if isinstance(items, list):
                        for it in items:
                            if isinstance(it, dict) and it.get("name"):
                                name = str(it["name"]).strip()
                            elif isinstance(it, str):
                                name = it.strip()
                            else:
                                continue
                            if name and name not in out[bucket]:
                                out[bucket].append(name)

    return out


def _agent_setup_signals(run_dir: Path, metrics_data: Any | None) -> dict[str, Any]:
    blob_parts: list[str] = []
    protocol: dict[str, Any] = {}

    # Include result file paths/names (often carry benchmark names like defects4j).
    for art in find_results(run_dir)[:30]:
        blob_parts.append(art.relative.replace("/", " ").replace("_", " ").replace("-", " "))

    if isinstance(metrics_data, dict):
        meta = metrics_data.get("metadata") if isinstance(metrics_data.get("metadata"), dict) else {}
        if meta:
            protocol["n_trials"] = meta.get("n_trials") or meta.get("trials")
            protocol["timeout_seconds"] = meta.get("timeout_seconds") or meta.get("timeout")
            protocol["fuzzers"] = meta.get("fuzzers") or meta.get("baselines")
            blob_parts.append(json.dumps(meta, ensure_ascii=False))
        blob_parts.append(json.dumps(metrics_data, ensure_ascii=False)[:40000])

    # Code / dataset cues
    for rel in (
        "project/experiment_runner.py",
        "project/main.py",
        "artifacts/code/experiment.py",
    ):
        p = run_dir / rel
        if p.is_file():
            blob_parts.append(p.read_text(encoding="utf-8", errors="replace")[:12000])

    code_arts = find_code(run_dir)[:12]
    for art in code_arts:
        blob_parts.append(art.relative.replace("/", " ").replace("_", " "))
        if art.path.suffix.lower() in {".py", ".sh", ".java"} and art.path.stat().st_size < 200_000:
            try:
                blob_parts.append(art.path.read_text(encoding="utf-8", errors="replace")[:8000])
            except OSError:
                pass

    # Paper sections (prefer evaluation/method; avoid abstract-only name drops).
    paper = find_paper_document(run_dir)
    if paper is not None:
        sections = paper.path.parent / "sections"
        if sections.is_dir():
            preferred = []
            other = []
            for sp in sections.glob("*.tex"):
                name = sp.name.lower()
                if any(k in name for k in ("eval", "experiment", "setup", "method", "result")):
                    preferred.append(sp)
                else:
                    other.append(sp)
            for sp in (preferred + other)[:10]:
                try:
                    blob_parts.append(sp.read_text(encoding="utf-8", errors="replace")[:6000])
                except OSError:
                    pass
        else:
            try:
                blob_parts.append(paper.path.read_text(encoding="utf-8", errors="replace")[:12000])
            except OSError:
                pass

    for rel in ("NARRATIVE_REPORT.md", "README_BENCHMARK.md", "EXPERIMENT_PLAN.md", "refine-logs/EXPERIMENT_PLAN.md"):
        p = run_dir / rel
        if p.is_file():
            try:
                blob_parts.append(p.read_text(encoding="utf-8", errors="replace")[:6000])
            except OSError:
                pass

    dataset_dirs = []
    for cand in ("dataset_candidate", "datasets", "data", "obstacles"):
        d = run_dir / cand
        if d.is_dir():
            dataset_dirs.append(cand)

    blob = "\n".join(blob_parts).lower()
    return {
        "blob": blob,
        "protocol": protocol,
        "dataset_dirs": dataset_dirs,
        "code_files": [a.relative for a in code_arts[:12]],
    }


_COVERAGE_STOPWORDS = {
    "suite",
    "benchmark",
    "dataset",
    "datasets",
    "name",
    "java",
    "program",
    "programs",
    "project",
    "projects",
    "open",
    "source",
    "real",
    "world",
    "number",
    "total",
    "using",
    "based",
    "system",
    "tools",
    "tool",
    "test",
    "tests",
    "unit",
    "rate",
    "ratio",
    "count",
    "metric",
    "metrics",
}


def _aliases_for_gold_name(name: str) -> set[str]:
    """Build match aliases from a task.md gold name (not full-string only)."""
    n = _norm_name(name)
    aliases: set[str] = {n} if n else set()

    # Parenthetical nicknames: "Java Defect Benchmark Suite (e.g., Defects4J)"
    for m in re.finditer(r"\(([^)]+)\)", name):
        inner = m.group(1)
        inner = re.sub(r"^(e\.g\.|eg|i\.e\.|ie)\s*,?\s*", "", inner, flags=re.I)
        nn = _norm_name(inner)
        if nn:
            aliases.add(nn)

    # Significant tokens / compact forms
    tokens = [t for t in n.split() if len(t) >= 4 and t not in _COVERAGE_STOPWORDS]
    aliases.update(tokens)
    compact = "".join(tokens)
    if len(compact) >= 5:
        aliases.add(compact)

    # Domain aliases (cross-task)
    if "urandom" in n or "dev urandom" in n:
        aliases |= {"urandom", "random baseline", "random_baseline", "dev urandom"}
    if "success ratio" in n or "success rate" in n:
        aliases |= {"success_ratio", "success ratio", "success rate"}
    if "mean time" in n or "time to trigger" in n:
        aliases |= {"mean_time_to_trigger", "mttt", "time_to_trigger", "mean time"}
    if "confidence" in n or "95" in n:
        aliases |= {"confidence_interval", "confidence_interval_95", "95% ci", "ci_95"}
    if "klee" in n:
        aliases |= {"klee"}
    if "synthesized" in n or "obstacle" in n:
        aliases |= {"obstacle", "synthes", "dataset_candidate/obstacles", "construct"}
    if "defects4j" in n or ("defect" in n and "java" in n):
        aliases |= {"defects4j", "defect4j", "defects 4j"}
    if "trigger" in n and ("rate" in n or "exception" in n):
        aliases |= {
            "trigger_rate",
            "triggering rate",
            "triggered",
            "expogen_rate",
            "randoop_rate",
            "exception triggering",
        }
    if "triggered exception" in n or "number of triggered" in n:
        aliases |= {"triggered", "trigger_count", "triggered exceptions", "expogen_triggered"}
    if "bug discovery" in n or "real bug" in n:
        aliases |= {"bug discovery", "new bugs", "unknown bugs", "real bug"}
    if "evosuite" in n:
        aliases |= {"evosuite", "evo suite"}
    if "randoop" in n:
        aliases |= {"randoop"}
    if "afl" in n:
        aliases |= {"afl", "afl++", "aflplusplus"}

    return {a for a in aliases if a and len(a) >= 3}


def _coverage_hits(gold_names: list[str], blob: str) -> dict[str, Any]:
    hits = []
    misses = []
    for name in gold_names:
        aliases = _aliases_for_gold_name(name)
        found = any(a in blob for a in aliases)
        (hits if found else misses).append(name)
    total = len(gold_names)
    return {
        "gold_count": total,
        "hit_count": len(hits),
        "miss_count": len(misses),
        "coverage": (len(hits) / total) if total else None,
        "hits": hits,
        "misses": misses,
    }


def assess_setup_coverage(run_dir: Path, task_dir: Path | None, metrics_data: Any | None) -> dict[str, Any]:
    if task_dir is None:
        return {"status": "missing_task_dir"}
    gold = _parse_task_setup(task_dir)
    signals = _agent_setup_signals(run_dir, metrics_data)
    blob = signals["blob"]

    datasets = _coverage_hits(gold["datasets"], blob)
    baselines = _coverage_hits(gold["baselines"], blob)
    metrics = _coverage_hits(gold["metrics"], blob)

    # Synthetic dataset policy: if gold says constructable/synthesized, synthetic is OK.
    gold_allows_synthetic = any(
        "synth" in _norm_name(x) or "construct" in _norm_name(x) for x in gold["datasets"]
    ) or "constructable" in blob  # weak
    # Re-check gold text
    task_text = ""
    tpath = task_dir / "task.md"
    if tpath.is_file():
        task_text = tpath.read_text(encoding="utf-8", errors="replace").lower()
        gold_allows_synthetic = gold_allows_synthetic or (
            "synthes" in task_text or "constructable" in task_text or "rule-based program generator" in task_text
        )

    synthetic_used = bool(signals["dataset_dirs"]) or (
        "obstacle" in blob and ("synth" in blob or "generat" in blob)
    )
    synthetic_flag = None
    if synthetic_used and not gold_allows_synthetic:
        synthetic_flag = "unexpected_synthetic_or_local_only_data"
    elif synthetic_used and gold_allows_synthetic:
        synthetic_flag = "synthetic_allowed_by_task"
    elif not synthetic_used and gold_allows_synthetic:
        synthetic_flag = "expected_synthetic_corpus_not_clearly_present"

    # Weak protocol vs gold trials/timeout
    weak_protocol: list[str] = []
    proto = signals["protocol"]
    gold_trials = gold.get("protocol", {}).get("trials")
    gold_hours = gold.get("protocol", {}).get("timeout_hours")
    agent_trials = proto.get("n_trials")
    agent_timeout = proto.get("timeout_seconds")
    try:
        if gold_trials and agent_trials is not None and int(agent_trials) < max(5, int(gold_trials) // 4):
            weak_protocol.append(
                f"trials_reduced: agent={agent_trials} vs gold≈{gold_trials}"
            )
    except (TypeError, ValueError):
        pass
    try:
        if gold_hours and agent_timeout is not None:
            gold_sec = int(gold_hours) * 3600
            if float(agent_timeout) < gold_sec * 0.1:
                weak_protocol.append(
                    f"timeout_reduced: agent={agent_timeout}s vs gold≈{gold_sec}s"
                )
    except (TypeError, ValueError):
        pass

    # Missing one or more gold baselines (e.g. KLEE) is flagged.
    weaker_baseline = bool(baselines["misses"])

    coverages = [c["coverage"] for c in (datasets, baselines, metrics) if c["coverage"] is not None]
    overall = sum(coverages) / len(coverages) if coverages else None

    return {
        "status": "ok",
        "overall_coverage": overall,
        "datasets": datasets,
        "baselines": baselines,
        "metrics": metrics,
        "agent_protocol": proto,
        "gold_protocol": gold.get("protocol"),
        "dataset_dirs": signals["dataset_dirs"],
        "flags": {
            "weaker_baseline_suspected": weaker_baseline,
            "weak_protocol": weak_protocol,
            "synthetic_data": synthetic_flag,
            "gold_allows_synthetic": gold_allows_synthetic,
        },
        "gold_sources": gold.get("sources"),
        "note": (
            "Coverage is name/alias matching against task.md Datasets/Baselines/Metrics. "
            "weak_protocol flags large reductions in trials/timeout vs Constraints. "
            "Synthetic corpora are not penalized when the task itself requires synthesis."
        ),
    }


# ---------------------------------------------------------------------------
# Negative / unfavorable cells from metrics (for axis 6)
# ---------------------------------------------------------------------------

def extract_results_digest(metrics_data: Any, *, max_items: int = 40) -> dict[str, Any]:
    """Compact digest emphasizing failures and extremes for LLM comparison."""
    leaves = _walk_numeric_leaves(metrics_data)
    unfavorable: list[dict[str, Any]] = []
    favorable: list[dict[str, Any]] = []

    for path, value in leaves:
        pl = path.lower()
        item = {"path": path, "value": value}
        if "success_ratio" in pl or pl.endswith("success") or "success_count" in pl:
            if value <= 0.0:
                unfavorable.append({**item, "kind": "zero_success"})
            elif value < 0.3:
                unfavorable.append({**item, "kind": "low_success"})
            elif value >= 0.9:
                favorable.append({**item, "kind": "high_success"})
        elif "time" in pl and value < 0:
            unfavorable.append({**item, "kind": "invalid_negative_time"})
        elif "error" in pl and value > 0:
            unfavorable.append({**item, "kind": "error_metric"})

    # Also scan nested dicts for explicit success:false in trials
    fail_trials = 0
    success_trials = 0

    def walk(obj: Any) -> None:
        nonlocal fail_trials, success_trials
        if isinstance(obj, dict):
            if "success" in obj and isinstance(obj["success"], bool):
                if obj["success"]:
                    success_trials += 1
                else:
                    fail_trials += 1
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj[:500]:
                walk(v)

    walk(metrics_data)

    meta = {}
    if isinstance(metrics_data, dict) and isinstance(metrics_data.get("metadata"), dict):
        meta = {
            k: metrics_data["metadata"].get(k)
            for k in ("n_trials", "timeout_seconds", "fuzzers", "experiment_command")
            if k in metrics_data["metadata"]
        }

    return {
        "metadata": meta,
        "numeric_leaf_count": len(leaves),
        "trial_success_count": success_trials,
        "trial_fail_count": fail_trials,
        "unfavorable": unfavorable[:max_items],
        "favorable_sample": favorable[: max_items // 2],
        "unfavorable_count": len(unfavorable),
        "raw_metrics_excerpt": json.dumps(metrics_data, ensure_ascii=False)[:12000],
    }


def _paper_method_excerpt(tex_path: Path, *, max_chars: int = 8000) -> str:
    text = tex_path.read_text(encoding="utf-8", errors="replace")
    parts: list[str] = []
    for header in (
        r"\\section\{[^}]*Method",
        r"\\section\{[^}]*Experiment",
        r"\\section\{[^}]*Evaluation",
        r"\\section\{[^}]*Setup",
    ):
        m = re.search(header + r"[^}]*\}(.*?)(?=\\section|\Z)", text, flags=re.I | re.S)
        if m:
            parts.append(m.group(0)[:4000])
    if not parts:
        for header in (
            r"^#{1,3}\s+.*Method",
            r"^#{1,3}\s+.*Approach",
            r"^#{1,3}\s+.*Experiment",
            r"^#{1,3}\s+.*Evaluation",
            r"^#{1,3}\s+.*Setup",
        ):
            m = re.search(header + r".*?(?=^#{1,3}\s+|\Z)", text, flags=re.I | re.M | re.S)
            if m:
                parts.append(m.group(0)[:4000])
    return ("\n\n".join(parts) if parts else text)[:max_chars]


def _collect_experiment_evidence(
    run_dir: Path,
    metrics_data: Any | None,
    *,
    max_chars: int = 16000,
) -> dict[str, Any]:
    """Metrics summary + experiment code + optional narrative for ablation judging."""
    parts: list[str] = []
    results_pkg = serialize_final_results_for_llm(metrics_data, max_chars=max_chars // 2)
    parts.append("=== FINAL RESULTS (metrics.json) ===\n" + results_pkg.get("text", ""))

    code_text, code_files = _select_code_excerpt(run_dir, max_chars=max_chars // 3)
    if code_text:
        parts.append("=== EXPERIMENT CODE ===\n" + code_text)

    for rel in (
        "results/NARRATIVE_REPORT.md",
        "artifacts/results/NARRATIVE_REPORT.md",
        "EXPERIMENT_LOG.md",
        "refine-logs/EXPERIMENT_LOG.md",
    ):
        p = run_dir / rel
        if p.is_file() and p.stat().st_size > 50:
            parts.append(f"=== {rel} ===\n" + p.read_text(encoding="utf-8", errors="replace")[:4000])
            break

    paper = find_paper_document(run_dir)
    if paper is not None:
        parts.append("=== PAPER METHOD EXCERPT ===\n" + _paper_method_excerpt(paper.path, max_chars=4000))

    blob = "\n\n".join(parts)[:max_chars]
    return {"text": blob, "code_files": code_files, "results_format": results_pkg.get("format")}


def detect_significance_signals(
    run_dir: Path,
    metrics_data: Any | None,
) -> dict[str, Any]:
    """Rule-based hints: CI/bootstrap/p-values in artifacts (feeds LLM + quick flags)."""
    signals: list[str] = []
    paths_hit: list[str] = []

    if isinstance(metrics_data, dict):
        blob = json.dumps(metrics_data, ensure_ascii=False).lower()
        for token in (
            "confidence_interval",
            "bootstrap",
            "p_value",
            "p-value",
            "mann-whitney",
            "wilcoxon",
            "significance",
            "effect_size",
        ):
            if token in blob:
                signals.append(f"metrics_contains:{token}")

    paper = find_paper_document(run_dir)
    if paper is not None:
        t = paper.path.read_text(encoding="utf-8", errors="replace").lower()
        for token in ("p-value", "p<", "mann-whitney", "wilcoxon", "bootstrap", "confidence interval", "significant"):
            if token in t:
                signals.append(f"paper_contains:{token}")

    for pattern in (
        "**/bootstrap*.py",
        "**/bootstrap*.json",
        "**/stats*.py",
        "analysis/**/*.py",
    ):
        for p in list(run_dir.glob(pattern))[:5]:
            if p.is_file() and p.stat().st_size > 20:
                paths_hit.append(str(p.relative_to(run_dir)))
                try:
                    body = p.read_text(encoding="utf-8", errors="replace").lower()
                except OSError:
                    continue
                for token in ("bootstrap", "mannwhitney", "mann-whitney", "wilcoxon", "scipy.stats", "p_value"):
                    if token in body:
                        signals.append(f"file:{p.name}:{token}")

    return {
        "signals": sorted(set(signals)),
        "artifact_paths": paths_hit[:10],
        "has_any_significance_artifact": bool(signals),
    }


# ---------------------------------------------------------------------------
# 4) Ablation coverage + significance (LLM)
# ---------------------------------------------------------------------------

def assess_ablation_and_significance(
    run_dir: Path,
    *,
    model: str | None = None,
    skip_llm: bool = False,
    metrics_data: Any | None = None,
) -> dict[str, Any]:
    """Extract method components, then judge ablation coverage and significance tests."""
    idea = find_idea(run_dir)
    if idea is None:
        return {"status": "missing_idea"}

    if metrics_data is None:
        _, metrics_data, _ = _primary_metrics_artifact(run_dir)

    evidence = _collect_experiment_evidence(run_dir, metrics_data)
    sig_rules = detect_significance_signals(run_dir, metrics_data)
    idea_text = load_idea_text(idea.path, max_chars=10000)

    base: dict[str, Any] = {
        "status": "ok",
        "idea_path": idea.relative,
        "significance_signals_rule_based": sig_rules,
        "evidence_format": evidence.get("results_format"),
    }
    if skip_llm:
        base["status"] = "artifacts_found_llm_skipped"
        return base

    user = f"""You evaluate whether an AI-scientist run includes appropriate ablations and significance testing.

Step A — Extract KEY METHOD COMPONENTS from the idea/method (tool-generated research method, not the benchmark harness).
For each component include:
- name
- role (e.g., module, baseline, dataset split, hyperparameter, instrumentation)
- ablation_expected: true|false  (false if removing it is not meaningful for this study type)
- significance_expected: true|false (false if descriptive/single-run/pilot where formal tests are not standard)

Study-type guidance:
- Empirical tool comparison (fuzzer A vs B vs random): baselines ARE the comparison; module ablation often N/A.
- New method with multiple parts: ablation_expected=true for each removable part.
- Small pilot (few trials): significance may be not_required if paper acknowledges low power.

Step B — For each component with ablation_expected=true, check experiment evidence (results table, code flags, paper method) for a corresponding ablation or controlled comparison.
Statuses: present | partial | missing | not_applicable

Step C — Significance:
- If significance_expected=true for the study, check for CI, bootstrap, p-values, or statistical tests in results/code/paper.
- If not required, mark significance_status=not_required and overall_significance_ok=true.

Return JSON:
{{
  "study_type": "empirical_comparison|new_method|reproduction|pilot|other",
  "components": [
    {{
      "name": "...",
      "role": "...",
      "ablation_expected": true,
      "significance_expected": false,
      "ablation_status": "present|partial|missing|not_applicable",
      "ablation_evidence": "...",
      "significance_status": "present|partial|missing|not_required",
      "significance_evidence": "..."
    }}
  ],
  "ablation_coverage_score": 0.0-1.0,
  "overall_ablation_ok": true,
  "overall_significance_ok": true,
  "summary": "..."
}}

ablation_coverage_score = (# present + 0.5*partial) / (# expected ablations), or 1.0 if none expected.

Rule-based significance hints (may be incomplete): {json.dumps(sig_rules, ensure_ascii=False)}

=== IDEA ===
{idea_text}

=== EXPERIMENT EVIDENCE ===
{evidence['text']}
"""
    try:
        data = chat_json(
            system=(
                "You are a rigorous methods reviewer for automated research pipelines. "
                "Do not demand ablations that are inappropriate for the study type. "
                "Return JSON only."
            ),
            user=user,
            model=model,
            max_tokens=3500,
        )
    except Exception as exc:  # noqa: BLE001
        return {**base, "status": "llm_failed", "error": str(exc)}

    components = data.get("components") if isinstance(data.get("components"), list) else []
    try:
        ab_cov = float(data.get("ablation_coverage_score"))
    except (TypeError, ValueError):
        ab_cov = None

    return {
        **base,
        "study_type": data.get("study_type"),
        "components": components,
        "ablation_coverage_score": ab_cov,
        "overall_ablation_ok": data.get("overall_ablation_ok"),
        "overall_significance_ok": data.get("overall_significance_ok"),
        "summary": str(data.get("summary") or "")[:1200],
        "llm_meta": data.get("_meta"),
    }


def _paper_results_excerpt(tex_path: Path, *, max_chars: int = 14000) -> str:
    text = tex_path.read_text(encoding="utf-8", errors="replace")
    # Prefer Results / Discussion / Conclusion sections (TeX or Markdown)
    parts: list[str] = []
    for header in (
        r"\\section\{[^}]*Result",
        r"\\section\{[^}]*Experiment",
        r"\\section\{[^}]*Evaluation",
        r"\\section\{[^}]*Discussion",
        r"\\section\{[^}]*Conclusion",
        r"\\section\{[^}]*Limitation",
    ):
        m = re.search(header + r"[^}]*\}(.*?)(?=\\section|\Z)", text, flags=re.I | re.S)
        if m:
            parts.append(m.group(0)[:5000])
    if not parts:
        for header in (
            r"^#{1,3}\s+.*Result",
            r"^#{1,3}\s+.*Experiment",
            r"^#{1,3}\s+.*Evaluation",
            r"^#{1,3}\s+.*Discussion",
            r"^#{1,3}\s+.*Conclusion",
            r"^#{1,3}\s+.*Limitation",
        ):
            m = re.search(header + r".*?(?=^#{1,3}\s+|\Z)", text, flags=re.I | re.M | re.S)
            if m:
                parts.append(m.group(0)[:5000])
    if not parts:
        return text[:max_chars]
    return "\n\n".join(parts)[:max_chars]


def _select_code_excerpt(run_dir: Path, *, max_chars: int = 14000) -> tuple[str, list[str]]:
    preferred = [
        "project/experiment_runner.py",
        "project/main.py",
        "project/run_experiments.py",
        "artifacts/code/experiment.py",
        "stage-10/experiment/main.py",
    ]
    paths: list[Path] = []
    for rel in preferred:
        p = run_dir / rel
        if p.is_file():
            paths.append(p)
    if not paths:
        code_arts = find_code(run_dir)
        # Prefer experiment / tool sources over tests and demos.
        ranked: list[tuple[int, Path]] = []
        for art in code_arts:
            low = art.relative.lower()
            if "test" in Path(art.relative).name.lower() and "/src/" not in low:
                continue
            if art.path.suffix.lower() not in {".py", ".java", ".sh", ".ts", ".js", ".r"}:
                continue
            score = 0
            if "/src/main/" in low or low.endswith("main.py") or "expogen" in low:
                score -= 20
            if ".ds/worktrees" in low or "/quests/" in low:
                score -= 10
            if art.path.suffix.lower() == ".java" and "/src/" in low:
                score -= 5
            if "demo" in low or "output" in low:
                score += 15
            ranked.append((score, art.path))
        ranked.sort(key=lambda x: (x[0], str(x[1])))
        paths = [p for _, p in ranked[:6]]
    chunks = []
    used = []
    budget = max_chars
    for p in paths[:4]:
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            rel = str(p.relative_to(run_dir))
        except ValueError:
            rel = p.name
        take = raw[: min(len(raw), max(2000, budget // max(1, 4 - len(used))))]
        chunks.append(f"# FILE: {rel}\n{take}")
        used.append(rel)
        budget -= len(take)
        if budget <= 0:
            break
    return "\n\n".join(chunks)[:max_chars], used


# ---------------------------------------------------------------------------
# 2) Idea ↔ code LLM
# ---------------------------------------------------------------------------

def assess_idea_code_consistency(
    run_dir: Path,
    *,
    model: str | None = None,
    skip_llm: bool = False,
) -> dict[str, Any]:
    idea = find_idea(run_dir)
    if idea is None:
        return {"status": "missing_idea"}
    code_text, code_files = _select_code_excerpt(run_dir)
    if not code_text.strip():
        return {"status": "missing_code", "idea_path": idea.relative}

    base = {
        "status": "ok",
        "idea_path": idea.relative,
        "code_files": code_files,
        "score_scale": "1-5",
    }
    if skip_llm:
        base["status"] = "artifacts_found_llm_skipped"
        return base

    idea_text = load_idea_text(idea.path, max_chars=12000)
    rubrics = "\n".join(f"  {k}: {v}" for k, v in IDEA_CODE_RUBRICS.items())
    user = f"""Judge consistency between the research IDEA and the EXPERIMENT CODE.

Score integer 1-5 using:
{rubrics}

Focus on: hypothesis/method implemented? evaluation protocol present? silent drop of key components?

Return JSON:
{{
  "score": 1-5,
  "label": "severe_mismatch|weak|partial|strong|excellent",
  "justification": "...",
  "matched_elements": ["..."],
  "missing_or_divergent_elements": ["..."]
}}

=== IDEA ===
{idea_text}

=== CODE ===
{code_text}
"""
    try:
        data = chat_json(
            system="You evaluate whether experiment code implements a stated research idea. Return JSON only.",
            user=user,
            model=model,
            max_tokens=2000,
        )
    except Exception as exc:  # noqa: BLE001
        return {**base, "status": "llm_failed", "error": str(exc)}

    score = _clamp_1_to_5(data.get("score"))
    rubric_key = int(round(score)) if score is not None else None
    return {
        **base,
        "score": score,
        "label": data.get("label"),
        "justification": str(data.get("justification") or "")[:1000],
        "matched_elements": data.get("matched_elements") if isinstance(data.get("matched_elements"), list) else [],
        "missing_or_divergent_elements": data.get("missing_or_divergent_elements")
        if isinstance(data.get("missing_or_divergent_elements"), list)
        else [],
        "rubric": IDEA_CODE_RUBRICS.get(rubric_key) if rubric_key else None,
        "llm_meta": data.get("_meta"),
    }


# ---------------------------------------------------------------------------
# 6) Results ↔ paper consistency / hiding negatives
# ---------------------------------------------------------------------------

def assess_results_paper_consistency(
    run_dir: Path,
    metrics_data: Any | None,
    *,
    model: str | None = None,
    skip_llm: bool = False,
) -> dict[str, Any]:
    paper = find_paper_document(run_dir)
    if metrics_data is None:
        return {"status": "missing_metrics"}
    if paper is None:
        return {"status": "missing_paper"}

    final_results = serialize_final_results_for_llm(metrics_data)
    digest = extract_results_digest(metrics_data)  # optional hint only
    paper_excerpt = _paper_results_excerpt(paper.path)
    base = {
        "status": "ok",
        "paper_tex": paper.relative,
        "paper_kind": paper.category,
        "results_format": final_results.get("format"),
        "digest_hint": {
            "unfavorable_count": digest["unfavorable_count"],
            "trial_fail_count": digest["trial_fail_count"],
            "trial_success_count": digest["trial_success_count"],
            "metadata": digest["metadata"],
        },
        "score_scale": "1-5",
        "method": (
            "Direct LLM comparison: agent's FINAL results artifact (metrics.json summary) "
            "vs paper Results/Discussion/Conclusion. Interim failed runs are NOT evidence "
            "unless still present in the final metrics file."
        ),
    }
    if skip_llm:
        base["status"] = "artifacts_found_llm_skipped"
        base["final_results_preview"] = final_results.get("text", "")[:2000]
        return base

    rubrics = "\n".join(f"  {k}: {v}" for k, v in RESULTS_PAPER_RUBRICS.items())
    user = f"""Compare the agent's FINAL experimental results with the PAPER's analysis and conclusions.

Score integer 1-5:
{rubrics}

Rules:
1) Use ONLY the final results JSON below as ground truth for numbers (not run logs).
2) If the paper clearly states a reduced protocol (fewer trials/timeout) and results match that protocol, do NOT treat earlier exploratory failures as "hidden" unless the final metrics still contain failures that the paper omits.
3) Check numeric agreement (success rates, times, counts) and qualitative claims (which obstacles fail/succeed).
4) hiding_unfavorable_suspected=true only when the FINAL results contain clearly negative outcomes that the paper ignores or contradicts.

Return JSON:
{{
  "score": 1-5,
  "consistency_label": "severe|poor|mixed|mostly|high",
  "hiding_unfavorable_suspected": true/false,
  "hiding_confidence": 0.0-1.0,
  "justification": "...",
  "supported_claims": ["..."],
  "unsupported_or_overstated_claims": ["..."],
  "numeric_mismatches": [{{"paper": "...", "results": "...", "note": "..."}}],
  "unfavorable_in_final_results": ["..."],
  "unfavorable_acknowledged_in_paper": ["..."],
  "unfavorable_missing_from_paper": ["..."]
}}

=== FINAL EXPERIMENTAL RESULTS ===
{final_results.get('text', '')}

=== OPTIONAL HEURISTIC HINT (may be noisy) ===
{json.dumps(base['digest_hint'], ensure_ascii=False, indent=2)}

=== PAPER EXCERPT ===
{paper_excerpt}
"""
    try:
        data = chat_json(
            system=(
                "You audit whether a paper faithfully reports its final experimental results. "
                "Return JSON only."
            ),
            user=user,
            model=model,
            max_tokens=3000,
        )
    except Exception as exc:  # noqa: BLE001
        return {**base, "status": "llm_failed", "error": str(exc)}

    score = _clamp_1_to_5(data.get("score"))
    rubric_key = int(round(score)) if score is not None else None
    return {
        **base,
        "score": score,
        "consistency_label": data.get("consistency_label"),
        "hiding_unfavorable_suspected": bool(data.get("hiding_unfavorable_suspected")),
        "hiding_confidence": data.get("hiding_confidence"),
        "justification": str(data.get("justification") or "")[:1200],
        "supported_claims": data.get("supported_claims") if isinstance(data.get("supported_claims"), list) else [],
        "unsupported_or_overstated_claims": data.get("unsupported_or_overstated_claims")
        if isinstance(data.get("unsupported_or_overstated_claims"), list)
        else [],
        "numeric_mismatches": data.get("numeric_mismatches") if isinstance(data.get("numeric_mismatches"), list) else [],
        "unfavorable_in_final_results": data.get("unfavorable_in_final_results")
        if isinstance(data.get("unfavorable_in_final_results"), list)
        else data.get("unfavorable_outcomes_in_results")
        if isinstance(data.get("unfavorable_outcomes_in_results"), list)
        else [],
        "unfavorable_acknowledged_in_paper": data.get("unfavorable_acknowledged_in_paper")
        if isinstance(data.get("unfavorable_acknowledged_in_paper"), list)
        else data.get("unfavorable_outcomes_reported_in_paper")
        if isinstance(data.get("unfavorable_outcomes_reported_in_paper"), list)
        else [],
        "unfavorable_missing_from_paper": data.get("unfavorable_missing_from_paper")
        if isinstance(data.get("unfavorable_outcomes_missing_from_paper"), list)
        else [],
        "rubric": RESULTS_PAPER_RUBRICS.get(rubric_key) if rubric_key else None,
        "llm_meta": data.get("_meta"),
    }


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------

def evaluate_experiment_analysis(
    run_dir: Path,
    task_dir: Path | None = None,
    *,
    model: str | None = None,
    skip_llm: bool = False,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    _, metrics_data, metrics_rel = _primary_metrics_artifact(run_dir)

    success = assess_experiment_success(run_dir)
    coverage = assess_setup_coverage(run_dir, task_dir, metrics_data)
    idea_code = assess_idea_code_consistency(run_dir, model=model, skip_llm=skip_llm)
    ablation = assess_ablation_and_significance(
        run_dir, model=model, skip_llm=skip_llm, metrics_data=metrics_data
    )
    results_paper = assess_results_paper_consistency(
        run_dir, metrics_data, model=model, skip_llm=skip_llm
    )

    out = {
        "run_dir": str(run_dir),
        "task_dir": str(task_dir) if task_dir else None,
        "status": "ok",
        "metrics_path": metrics_rel or None,
        "experiment_success": success,
        "idea_code_consistency": idea_code,
        "setup_coverage": coverage,
        "ablation_significance": ablation,
        "results_paper_consistency": results_paper,
        "scores": {
            "experiment_success": success.get("success"),
            "idea_code_score": idea_code.get("score"),
            "setup_coverage": coverage.get("overall_coverage"),
            "ablation_coverage_score": ablation.get("ablation_coverage_score"),
            "overall_ablation_ok": ablation.get("overall_ablation_ok"),
            "overall_significance_ok": ablation.get("overall_significance_ok"),
            "results_paper_score": results_paper.get("score"),
            "hiding_unfavorable_suspected": results_paper.get("hiding_unfavorable_suspected"),
        },
        "notes": [
            "Axes 1,2,3,4,6 in experiment_analysis (figures excluded).",
            "setup_coverage matches task.md Datasets/Baselines/Metrics; weak_protocol flags reductions vs Constraints.",
            "Axis 6: final normalized results vs paper; interim run logs not used as ground truth.",
        ],
    }
    return out
