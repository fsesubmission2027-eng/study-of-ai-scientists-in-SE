"""Task-agnostic metrics helpers for benchmark validators and resume prompts.

Required metric *names* come from each task's ``seeds/agent/metrics.json``
(via ``TaskBenchmarkConfig.required_metrics``). Do not hard-code ASE-003
fuzzing fields (or any other task) into resume / continuation prompts.
"""

from __future__ import annotations

from pathlib import Path

# Common agent naming drift → canonical required key.
# Only consulted when the *task* lists that canonical key as required.
METRIC_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "success_ratio": ("success_ratio", "success_rate", "successes_ratio"),
    "mean_time_to_trigger": ("mean_time_to_trigger", "mean_time", "mean_ttt", "ttt"),
    "confidence_interval_95": (
        "confidence_interval_95",
        "ci_95",
        "success_rate_95ci",
        "time_95ci",
        "ci95",
    ),
    "test_validity_rate": ("test_validity_rate", "validity_rate"),
    "generated_test_count": ("generated_test_count", "total_tests", "n_tests"),
    "generation_failures": ("generation_failures", "invalid_tests"),
    "engine_execution_failures": (
        "engine_execution_failures",
        "execution_failures",
        "wasmtime_fail",
    ),
    "recall": ("recall", "Recall", "avg_recall"),
    "precision": ("precision", "Precision", "avg_precision"),
    "f1_score": ("f1_score", "f1", "F1", "F1-Score", "f1-score", "avg_f1"),
}


def aliases_for_metric(key: str) -> tuple[str, ...]:
    return METRIC_KEY_ALIASES.get(key, (key,))


def format_required_metrics_prompt_note(
    required_metrics: list[str],
    *,
    code_hint: bool = True,
) -> str:
    """Build a resume/continuation note listing *this task's* required metrics."""
    if required_metrics:
        parts: list[str] = []
        for key in required_metrics:
            aliases = aliases_for_metric(key)
            if len(aliases) > 1:
                alt = ", ".join(f"`{a}`" for a in aliases[1:])
                parts.append(f"`{key}` (or {alt})")
            else:
                parts.append(f"`{key}`")
        keys_text = ", ".join(parts)
        body = (
            "Metrics schema note: write metrics to `results/metrics.json` "
            "(also accepted: `experiment_results/metrics.json`, `project/metrics.json`) "
            "exposing (directly or via aliases) these **task-required** keys: "
            f"{keys_text}. "
            "When present, also follow `dataset_candidate/metrics.json` / "
            "`dataset_candidate/metrics_schema.json`."
        )
    else:
        body = (
            "Metrics schema note: write `results/metrics.json` "
            "(or `experiment_results/metrics.json` / `project/metrics.json`) "
            "with the metric keys required by this task (see "
            "`dataset_candidate/metrics.json` or "
            "`dataset_candidate/metrics_schema.json` when present)."
        )
    if code_hint:
        body += (
            " Implementation code must live under `project/*.py` "
            "(you may move/copy from `analysis/` or `dataset_candidate/`)."
        )
    return body


def format_required_metrics_prompt_note_for_task(
    task_dir: Path,
    *,
    code_hint: bool = True,
) -> str:
    from benchmark_task_config import load_task_benchmark_config

    cfg = load_task_benchmark_config(task_dir)
    return format_required_metrics_prompt_note(
        list(cfg.required_metrics or []),
        code_hint=code_hint,
    )
