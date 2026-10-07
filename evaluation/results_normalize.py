"""Normalize experiment results across frameworks for fair evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from framework_profile import FrameworkProfile, get_framework_profile
from paths import _load_manifest, _result_path_blocked, find_results


def _path_blocked(rel: str) -> bool:
    return _result_path_blocked(rel)


def walk_numeric_leaves(obj: Any, *, path: str = "") -> list[tuple[str, float]]:
    out: list[tuple[str, float]] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}" if path else str(k)
            out.extend(walk_numeric_leaves(v, path=p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj[:200]):
            out.extend(walk_numeric_leaves(v, path=f"{path}[{i}]"))
    elif isinstance(obj, bool):
        return out
    elif isinstance(obj, (int, float)):
        out.append((path, float(obj)))
    return out


def is_stub_metrics(data: Any) -> bool:
    if data is None:
        return True
    if isinstance(data, dict):
        keys = {str(k).lower() for k in data.keys()}
        if keys <= {"required_metrics", "metrics", "schema", "description", "name"}:
            vals = data.get("required_metrics") or data.get("metrics")
            if isinstance(vals, list) and all(isinstance(x, str) for x in vals):
                return True
            if isinstance(vals, dict) and not walk_numeric_leaves(vals):
                return True
        if data in ({}, {"metrics": {}}):
            return True
        if set(keys) == {"metrics"} and data.get("metrics") in ({}, None, []):
            return True
    if isinstance(data, list) and not data:
        return True
    return len(walk_numeric_leaves(data)) < 3


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None


_NPY_ARRAY_CAP = 32
_NPY_MAX_DEPTH = 8
_NPY_MAX_KEYS = 40


def _npy_to_builtin(obj: Any, depth: int = 0) -> Any:
    """Turn a pickled experiment_data.npy tree into JSON-safe numbers."""
    if depth > _NPY_MAX_DEPTH:
        return None
    try:
        import numpy as np
    except ImportError:
        return None
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for i, (k, v) in enumerate(obj.items()):
            if i >= _NPY_MAX_KEYS:
                break
            converted = _npy_to_builtin(v, depth + 1)
            if converted is not None:
                out[str(k)] = converted
        return out or None
    if isinstance(obj, np.ndarray):
        if obj.dtype == object:
            if obj.shape == ():
                return _npy_to_builtin(obj.item(), depth + 1)
            return _npy_to_builtin(obj.tolist(), depth + 1)
        if not np.issubdtype(obj.dtype, np.number):
            return None
        if obj.size > _NPY_ARRAY_CAP:
            flat = np.asarray(obj, dtype=float).ravel()
            finite = flat[np.isfinite(flat)]
            if finite.size < 3:
                return None
            return {
                "count": int(finite.size),
                "mean": float(finite.mean()),
                "min": float(finite.min()),
                "max": float(finite.max()),
            }
        return _npy_to_builtin(obj.tolist(), depth + 1)
    if isinstance(obj, (list, tuple)):
        items = [_npy_to_builtin(v, depth + 1) for v in obj[:_NPY_ARRAY_CAP]]
        items = [v for v in items if v is not None]
        return items or None
    if isinstance(obj, np.generic):
        if isinstance(obj, np.floating):
            value = float(obj)
            return None if value != value else value
        if isinstance(obj, np.integer):
            return int(obj)
        try:
            return _npy_to_builtin(obj.item(), depth + 1)
        except Exception:
            return None
    if isinstance(obj, bool):
        return None
    if isinstance(obj, float):
        return None if obj != obj else obj
    if isinstance(obj, int):
        return obj
    if isinstance(obj, str) and obj and len(obj) <= 200:
        return obj
    return None


def load_npy_results(path: Path) -> Any | None:
    """Load an AI-Scientist experiment_data.npy dict without raw pickle arrays."""
    try:
        import numpy as np
    except ImportError:
        return None
    try:
        arr = np.load(path, allow_pickle=True)
    except Exception:
        return None
    data = _npy_to_builtin(arr)
    if is_stub_metrics(data):
        return None
    return data


def load_text_results(path: Path) -> Any | None:
    try:
        raw = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not raw or raw in ("{}", "[]"):
        return None
    try:
        data = json.loads(raw)
        return data if not is_stub_metrics(data) else None
    except json.JSONDecodeError:
        # Non-JSON text: keep as wrapper if it has substance
        if len(raw) >= 40:
            return {"_text_results": raw[:12000]}
        return None


@dataclass
class NormalizedResults:
    status: str  # ok | missing | stub
    path: Path | None
    relative: str
    data: Any
    source_kind: str  # json | text | npy
    numeric_leaf_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "path": self.relative or None,
            "source_kind": self.source_kind,
            "numeric_leaf_count": self.numeric_leaf_count,
        }


def _score_candidate(path: Path, data: Any, rel: str) -> int:
    if is_stub_metrics(data):
        return -1
    leaves = len(walk_numeric_leaves(data))
    score = leaves
    name = path.name.lower()
    if "metrics" in name:
        score += 50
    if name == "results.json":
        score += 40
    if "summary" in name:
        score += 10
    if _path_blocked(rel):
        score -= 1000
    return score


def normalize_results(
    run_dir: Path,
    *,
    profile: FrameworkProfile | None = None,
) -> NormalizedResults:
    run_dir = run_dir.resolve()
    profile = profile or get_framework_profile(run_dir)

    best: tuple[int, Path, Any, str, str] | None = None

    for rel in profile.result_candidates:
        if "**" in rel:
            for path in run_dir.glob(rel):
                if not path.is_file():
                    continue
                r = str(path.relative_to(run_dir))
                if _path_blocked(r):
                    continue
                data = load_json(path)
                if data is None:
                    continue
                sc = _score_candidate(path, data, r)
                if sc < 0:
                    continue
                if best is None or sc > best[0]:
                    best = (sc, path, data, r, "json")
        else:
            path = run_dir / rel
            if not path.is_file():
                continue
            r = rel
            if _path_blocked(r):
                continue
            data = load_json(path)
            if data is None:
                continue
            sc = _score_candidate(path, data, r)
            if sc < 0:
                continue
            if best is None or sc > best[0]:
                best = (sc, path, data, r, "json")

    for rel in profile.result_text_candidates:
        path = run_dir / rel
        if not path.is_file():
            continue
        data = load_text_results(path)
        if data is None:
            continue
        sc = _score_candidate(path, data, rel) + 5
        if best is None or sc > best[0]:
            best = (sc, path, data, rel, "text")

    # Generic fallback (filtered). .npy is only a last resort: a substantive
    # metrics/results JSON must keep winning when both exist.
    npy_best: tuple[int, Path, Any, str, str] | None = None
    for art in find_results(run_dir):
        r = art.relative
        if _path_blocked(r):
            continue
        suffix = art.path.suffix.lower()
        if suffix == ".npy":
            data = load_npy_results(art.path)
            kind = "npy"
        elif suffix == ".json":
            data = load_json(art.path)
            kind = "json"
        elif suffix in {".txt", ".md"}:
            data = load_text_results(art.path)
            kind = "text"
        else:
            continue
        if data is None:
            continue
        sc = _score_candidate(art.path, data, r)
        if sc < 0:
            continue
        if kind == "npy":
            if npy_best is None or sc > npy_best[0]:
                npy_best = (sc, art.path, data, r, kind)
            continue
        if best is None or sc > best[0]:
            best = (sc, art.path, data, r, kind)
    if best is None and npy_best is not None:
        best = npy_best

    if best is None:
        return NormalizedResults(status="missing", path=None, relative="", data=None, source_kind="none")

    _, path, data, rel, kind = best
    leaves = len(walk_numeric_leaves(data))
    return NormalizedResults(
        status="ok",
        path=path,
        relative=rel,
        data=data,
        source_kind=kind,
        numeric_leaf_count=leaves,
    )


def summarize_metrics_table(metrics_data: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(metrics_data, dict):
        return rows
    results = metrics_data.get("results")
    if not isinstance(results, dict):
        return rows
    for category, levels in results.items():
        if not isinstance(levels, dict):
            continue
        for level, level_data in levels.items():
            if not isinstance(level_data, dict):
                continue
            meta = {k: level_data.get(k) for k in ("source", "category", "level") if k in level_data}
            for key, stats in level_data.items():
                if key in ("source", "category", "level") or not isinstance(stats, dict):
                    continue
                if not any(
                    stats.get(k) is not None
                    for k in ("success_ratio", "success_count", "mean_time_to_trigger", "trials")
                ):
                    continue
                rows.append(
                    {
                        **meta,
                        "category": meta.get("category") or category,
                        "level": meta.get("level") or level,
                        "condition": key,
                        "success_ratio": stats.get("success_ratio"),
                        "success_count": stats.get("success_count"),
                        "trials": stats.get("trials"),
                        "mean_time_to_trigger": stats.get("mean_time_to_trigger"),
                        "confidence_interval_95": stats.get("confidence_interval_95"),
                    }
                )
    return rows


def serialize_final_results_for_llm(
    metrics_data: Any,
    *,
    max_chars: int = 28000,
) -> dict[str, Any]:
    """Package final experiment results for LLM judges (schema-agnostic).

    Prefer a compact ASE-style summary_table when present; otherwise dump the
    raw JSON (or text wrapper) so non-ASE tools are not treated as empty.
    """
    if metrics_data is None:
        return {"status": "missing", "text": ""}
    if isinstance(metrics_data, dict) and "_text_results" in metrics_data:
        return {
            "status": "ok",
            "text": metrics_data["_text_results"][:max_chars],
            "format": "text_results",
        }

    table = summarize_metrics_table(metrics_data)
    if table:
        meta = metrics_data.get("metadata") if isinstance(metrics_data, dict) else None
        bundle: dict[str, Any] = {
            "metadata": meta,
            "summary_table_rows": len(table),
            "summary_table": table,
        }
        text = json.dumps(bundle, ensure_ascii=False, indent=2)
        if len(text) <= max_chars:
            return {"status": "ok", "text": text, "format": "metadata+summary_table"}
        table_trunc = table[: min(len(table), 80)]
        bundle["summary_table"] = table_trunc
        bundle["summary_table_truncated"] = len(table) > len(table_trunc)
        bundle["raw_excerpt"] = json.dumps(metrics_data, ensure_ascii=False)[: max_chars // 3]
        return {
            "status": "ok",
            "text": json.dumps(bundle, ensure_ascii=False, indent=2)[:max_chars],
            "format": "metadata+truncated_table+excerpt",
        }

    # Generic / cross-tool fallback: keep summary + compact raw JSON.
    if isinstance(metrics_data, dict):
        bundle = {}
        for key in ("summary", "metadata", "metrics", "overall", "scores"):
            if key in metrics_data:
                bundle[key] = metrics_data[key]
        raw = json.dumps(metrics_data, ensure_ascii=False, indent=2)
        if len(raw) <= max_chars:
            return {"status": "ok", "text": raw, "format": "raw_json"}
        # Prefer summary block, then truncated raw.
        if bundle:
            head = json.dumps(bundle, ensure_ascii=False, indent=2)
            remain = max(1000, max_chars - len(head) - 80)
            text = head + "\n\n/* raw_json_truncated */\n" + raw[:remain]
            return {
                "status": "ok",
                "text": text[:max_chars],
                "format": "summary+raw_json_truncated",
            }
        return {"status": "ok", "text": raw[:max_chars], "format": "raw_json_truncated"}

    text = json.dumps(metrics_data, ensure_ascii=False, indent=2)
    return {
        "status": "ok",
        "text": text[:max_chars],
        "format": "raw_json" if len(text) <= max_chars else "raw_json_truncated",
    }
