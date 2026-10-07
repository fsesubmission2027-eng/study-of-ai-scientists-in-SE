#!/usr/bin/env python3
"""Run EvoScientist on an ai_scientist_inputs benchmark task.

Prepares RESEARCH_BRIEF.md / research_request.md from task.md, starts the benchmark
Docker sandbox, and launches `EvoSci` inside the container with an autonomous prompt.
Does not modify EvoScientist upstream code.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS_ROOT = BENCHMARK_ROOT / "integrations"
ORCHESTRATOR_ROOT = BENCHMARK_ROOT / "orchestrator"
AI_SCIENTIST_ROOT = BENCHMARK_ROOT.parent / "AI-Scientist-v2"
DEFAULT_TASK_DIR = (
    Path.home()
    / "ai_scientist_inputs/ASE-2025-004_predicting_recheck_success_in_continuous"
)
DEFAULT_PROVIDER = "custom-openai"
DEFAULT_MODEL = "openai/gpt-5-mini"


sys.path.insert(0, str(ORCHESTRATOR_ROOT))
sys.path.insert(0, str(INTEGRATIONS_ROOT))

from agent_container import (  # noqa: E402
    BENCHMARK_AGENT_NATIVE_ENV,
    build_container_env,
    launch_agent,
    preflight_binary,
    preflight_python,
    preflight_scrub_proxy,
    resolve_binary,
    scrub_base_url,
    workdir_for_run,
)
from benchmark_task_config import load_task_benchmark_config  # noqa: E402
from evoscientist_docker import write_benchmark_env  # noqa: E402
from evoscientist_task_layout import (  # noqa: E402
    finalize_run_metadata,
    prepare_run_layout,
    refresh_aligned_runtime_docs,
    write_evoscientist_config,
    write_runtime_files,
)
from evoscientist_workflow import (  # noqa: E402
    DEFAULT_BG_POLL_SEC,
    DEFAULT_BG_WAIT_SEC,
    DEFAULT_MAX_AUTO_RESUME_ROUNDS,
    DEFAULT_MAX_IDENTICAL_RESUME_ROUNDS,
    build_resume_continuation_prompt,
    install_research_skills,
    preflight_research_skills,
)
from evoscientist_autoresume import (  # noqa: E402
    build_hard_continuation_prompt,
    classify_evosci_exit,
    issues_fingerprint,
    list_background_experiment_procs,
    sync_container_workspace_to_run_root,
    wait_for_background_experiments,
)
from path_alignment import preflight_dataset_volumes  # noqa: E402
from metrics_schema import aliases_for_metric  # noqa: E402
from sandbox import TaskSandbox  # noqa: E402
from seed_staging import shell_copy_agent_seeds  # noqa: E402
from benchmark_credentials import apply_benchmark_credentials, credentials_file_path, require_llm_api_key, resolve_model  # noqa: E402
from transient_retry import (  # noqa: E402
    add_transient_retry_arguments,
    probe_transient_failure,
    resolve_existing_run_dir,
    resolve_transient_retry_policy,
)


def load_api_env(env: dict[str, str]) -> dict[str, str]:
    merged = apply_benchmark_credentials(env)
    api_key = merged.get("CUSTOM_OPENAI_API_KEY") or merged.get("OPENAI_API_KEY", "")
    base_url = scrub_base_url(merged)
    provider = merged.get("EVOSCIENTIST_PROVIDER", DEFAULT_PROVIDER)
    model = resolve_model("evoscientist", env=merged)

    if not api_key:
        raise RuntimeError(
            "Missing API key. Set llm.api_key in "
            f"{credentials_file_path()} "
            "(or run: python3 integrations/benchmark_credentials.py --init)."
        )

    merged["CUSTOM_OPENAI_API_KEY"] = api_key
    # Keep /v1: EvoScientist OpenAI client posts to {base}/chat/completions.
    merged["CUSTOM_OPENAI_BASE_URL"] = base_url.rstrip("/")
    merged["OPENAI_API_KEY"] = api_key
    merged["OPENAI_BASE_URL"] = base_url.rstrip("/")
    merged["EVOSCIENTIST_PROVIDER"] = provider
    merged["EVOSCIENTIST_MODEL"] = model
    return merged


def _ensure_openai_v1_base_url(url: str) -> str:
    bare = (url or "").strip().rstrip("/")
    if not bare:
        return bare
    return bare if bare.endswith("/v1") else f"{bare}/v1"


def seed_container_workspace(sandbox: TaskSandbox, run_root: Path) -> None:
    from path_alignment import align_run_dataset_paths

    seeds_path = sandbox.seeds_path()
    req = f"{seeds_path}/requirements.txt"
    seeds_dir = sandbox.task_dir / "seeds"
    copy_cmd = shell_copy_agent_seeds(seeds_dir, f"{run_root}/dataset_candidate")
    sandbox.exec(
        f"mkdir -p {run_root}/dataset_candidate "
        f"{run_root}/project {run_root}/results {run_root}/paper && "
        f"{copy_cmd}",
        workdir=str(run_root),
    )
    code, stdout, stderr = sandbox.exec(
        f"test -f {req} && python3 -m pip install -r {req} || true",
        workdir=str(run_root),
    )
    if stdout.strip():
        print(stdout.strip())
    if stderr.strip() and code != 0:
        print(stderr.strip(), file=sys.stderr)
    align_run_dataset_paths(run_root, sandbox.env)


def build_evosci_command(
    evosci_bin: str,
    prompt: str,
    run_root: Path,
    *,
    resume_thread: str | None = None,
    model: str = "",
) -> list[str]:
    # DeepSeek via custom-openai (umodelverse) needs reasoning_content passback
    # that EvoScientist only mounts for provider=deepseek. Route through launcher.
    evosci_args = [
        "--workdir",
        str(run_root),
        "--ui",
        "cli",
        "--dangerous",
        "--auto-mode",
        "--auto-approve",
        "--no-thinking",
    ]
    if resume_thread:
        evosci_args.extend(["--resume", resume_thread])
    evosci_args.extend(["-p", prompt])

    if "deepseek" in model.lower():
        evosci_python = Path(evosci_bin).resolve().parent / "python3"
        launcher = INTEGRATIONS_ROOT / "evoscientist_launcher.py"
        return [str(evosci_python), str(launcher), *evosci_args]

    return [evosci_bin, *evosci_args]


def _metric_value_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        return bool(value)
    if isinstance(value, (list, tuple, str)):
        return bool(value)
    return True


_METRIC_NEST_KEYS = (
    "baseline",
    "afl",
    "aflpp",
    "libfuzzer",
    "improved",
    "metrics",
    "results",
    "fuzzer",
)


def _flatten_metric_node(node: object) -> list[dict]:
    if not isinstance(node, dict):
        return []
    nested_records: list[dict] = []
    for key in _METRIC_NEST_KEYS:
        child = node.get(key)
        if isinstance(child, dict):
            nested_records.extend(_flatten_metric_node(child))
    if nested_records:
        return nested_records
    # Leaf-ish metric dict (has numeric fields or known aliases).
    return [node]


def _collect_metric_records(data: object) -> list[dict]:
    """Normalize metrics.json into a flat list of metric dicts."""
    if isinstance(data, dict):
        if any(isinstance(v, dict) for v in data.values()):
            records: list[dict] = []
            for value in data.values():
                records.extend(_flatten_metric_node(value))
            return records or [data]
        return [data]
    if isinstance(data, list):
        records: list[dict] = []
        for item in data:
            records.extend(_flatten_metric_node(item))
        return records
    return []


def _record_has_metric(record: dict, key: str) -> bool:
    return any(_metric_value_present(record.get(alias)) for alias in aliases_for_metric(key))


def validate_run_deliverables(run_root: Path, task_dir: Path) -> tuple[bool, list[str]]:
    cfg = load_task_benchmark_config(task_dir)
    issues: list[str] = []

    if not (run_root / "todos.md").is_file() and not (run_root / "plan.md").is_file():
        issues.append("missing plan (todos.md or plan.md)")

    project = run_root / "project"
    if not project.is_dir() or not any(project.rglob("*.py")):
        issues.append("missing project/*.py")

    metrics_path = run_root / "results" / "metrics.json"
    if not metrics_path.is_file():
        issues.append("missing results/metrics.json")
    else:
        try:
            data = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append("results/metrics.json is invalid JSON")
        else:
            records = _collect_metric_records(data)
            if not records:
                issues.append("results/metrics.json has no metric records")
            else:
                for key in cfg.required_metrics:
                    if not any(_record_has_metric(record, key) for record in records):
                        issues.append(f"results/metrics.json missing or null {key}")

    if not (run_root / "paper" / "main.tex").is_file():
        issues.append("missing paper/main.tex")

    if not (run_root / "README.md").is_file():
        issues.append("missing README.md")

    return not issues, issues


def extract_thread_id_from_log(log_path: Path) -> str | None:
    if not log_path.is_file():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    match = re.search(r"Thread:\s*(\S+)", text)
    if match:
        return match.group(1)
    match = re.search(r"EvoSci --resume\s+(\S+)", text)
    if match:
        return match.group(1)
    return None


def launch_evosci(
    *,
    container_id: str,
    evosci_bin: str,
    run_root: Path,
    env: dict[str, str],
    log_path: Path,
    prompt: str,
    provider: str,
    model: str,
    resume_thread: str | None = None,
    append_log: bool = False,
) -> int:
    cmd = build_evosci_command(
        evosci_bin,
        prompt,
        run_root,
        resume_thread=resume_thread,
        model=model,
    )
    label = "resume" if resume_thread else "launch"
    print(f"[{label}] in-container:", " ".join(cmd[:8]), "<prompt...>")
    print(f"[{label}] log={log_path}")

    if append_log:
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(
                f"\n\n# EvoScientist resume {datetime.now().isoformat(timespec='seconds')}\n"
                f"# container={container_id}\n"
                f"# provider={provider} model={model}\n"
            )
            if resume_thread:
                log_file.write(f"# resume_thread={resume_thread}\n")
    else:
        with log_path.open("w", encoding="utf-8") as log_file:
            log_file.write(
                f"# EvoScientist launch {datetime.now().isoformat(timespec='seconds')}\n"
                f"# cwd={run_root}\n"
                f"# container={container_id}\n"
                f"# provider={provider} model={model}\n\n"
            )

    return launch_agent(
        container_id=container_id,
        cmd=cmd,
        cwd=run_root,
        env=env,
        log_path=log_path,
        append=True,
    )


def write_readme_benchmark(
    readme: Path,
    *,
    run_root: Path,
    container_id: str,
    docker_workdir: str,
    config_path: Path,
    provider: str,
    model: str,
    prompt_path: Path,
    thread_id: str | None,
    resume_prompt: str,
) -> None:
    resume_block = ["## Resume", ""]
    if thread_id:
        resume_block.extend(
            [
                f"Thread id: `{thread_id}`",
                "",
                "```bash",
                f"cd {BENCHMARK_ROOT}",
                "python3 integrations/run_evoscientist_task.py \\",
                f"  --task-dir {run_root.parent.parent} \\",
                f"  --resume-thread {thread_id} \\",
                f'  --resume-prompt "{resume_prompt}"',
                "```",
                "",
            ]
        )
    else:
        resume_block.extend(
            [
                "Check `evoscientist_run.log` for `Thread:` or `EvoSci --resume <id>`.",
                "",
            ]
        )

    readme.write_text(
        "\n".join(
            [
                "# EvoScientist benchmark run",
                "",
                f"- Prepared: {datetime.now().isoformat(timespec='seconds')}",
                f"- Container: `{container_id}`",
                f"- Workdir: `{docker_workdir}`",
                f"- Execution: in-container (aligned paths)",
                f"- EvoScientist config: `{config_path}`",
                f"- Provider/model: `{provider}` / `{model}`",
                "",
                "## Manual launch (if you skipped --launch)",
                "",
                "```bash",
                f"python3 {BENCHMARK_ROOT / 'integrations' / 'run_evoscientist_task.py'} \\",
                f"  --task-dir {run_root.parent.parent} --launch",
                "```",
                "",
                "The integration script appends extra tool-calling rules to the prompt on `--launch`.",
                "",
                *resume_block,
                "Docker container is kept running by default after launch (use `--no-keep-sandbox` "
                "or `--cleanup` to destroy it).",
                "",
            ]
        ),
        encoding="utf-8",
    )


def run_pipeline(task_dir: Path, args: argparse.Namespace) -> int:
    if not shutil.which("docker"):
        print("docker is required for EvoScientist benchmark experiment isolation.", file=sys.stderr)
        return 1

    api_env = os.environ.copy()
    evosci_bin: str | None = None
    if args.launch or (not args.prepare_only and os.environ.get(BENCHMARK_AGENT_NATIVE_ENV) != "1"):
        try:
            evosci_bin = resolve_binary("evoscientist", "EvoSci", api_env)
            if args.launch:
                api_env = load_api_env(os.environ)
        except (FileNotFoundError, RuntimeError) as exc:
            print(str(exc), file=sys.stderr)
            return 1

    provider = args.provider or api_env.get("EVOSCIENTIST_PROVIDER", DEFAULT_PROVIDER)
    model = args.model or api_env.get("EVOSCIENTIST_MODEL") or resolve_model("evoscientist", env=api_env)
    base_url = args.base_url or api_env.get("CUSTOM_OPENAI_BASE_URL", scrub_base_url(api_env))
    api_key = api_env.get("CUSTOM_OPENAI_API_KEY", "")

    try:
        existing_run = resolve_existing_run_dir(getattr(args, "run_dir", None))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    run_root, workspace_root = prepare_run_layout(task_dir, run_dir=existing_run)
    docker_workdir = workdir_for_run(run_root)
    if existing_run is not None:
        print(f"[prepare] reusing run_dir={run_root}")
    # Register metering before writing EvoScientist config so base_url is metered.
    from agent_container import apply_run_metering_to_env

    api_env = apply_run_metering_to_env(api_env, run_root=run_root, for_container=True)
    if not args.base_url:
        base_url = (
            api_env.get("OPENAI_BASE_URL")
            or api_env.get("OPENAI_API_BASE")
            or api_env.get("CUSTOM_OPENAI_BASE_URL")
            or base_url
        )
    base_url = _ensure_openai_v1_base_url(base_url)
    api_env["CUSTOM_OPENAI_BASE_URL"] = base_url
    api_env["OPENAI_BASE_URL"] = base_url
    api_env["OPENAI_API_BASE"] = base_url
    print(f"[prepare] run_root={run_root}")
    print(f"[prepare] workdir={docker_workdir}")
    print(f"[prepare] provider={provider} model={model}")
    print(f"[prepare] base_url={base_url}")
    ok_skills, skills_msg = install_research_skills(run_root)
    print(f"[prepare] {skills_msg}")
    if not ok_skills:
        return 1

    sandbox = TaskSandbox(task_dir, agent_tool="evoscientist")
    container_id: str | None = None
    returncode = 0

    try:
        container_id = sandbox.start(agent_tool="evoscientist", run_root=run_root)
        print(f"[sandbox] container_id={container_id}")

        write_benchmark_env(
            run_root,
            container_id=container_id,
            docker_workdir=docker_workdir,
            host_run_root=run_root,
        )
        config_path = write_evoscientist_config(
            run_root,
            provider=provider,
            model=model,
            api_key=api_key or "prepare-only",
            base_url=base_url,
        )
        prompt_path = write_runtime_files(
            run_root,
            task_dir,
            docker_workdir=docker_workdir,
            task_env=sandbox.env,
        )
        seed_container_workspace(sandbox, run_root)
        prompt_path = refresh_aligned_runtime_docs(
            run_root,
            task_dir,
            sandbox.env,
            docker_workdir=docker_workdir,
        )

        ok, preflight_msg = preflight_python(container_id, run_root)
        print(f"[preflight] {preflight_msg}")
        if not ok:
            return 1
        if evosci_bin:
            ok_bin, bin_msg = preflight_binary(container_id, evosci_bin, cwd=run_root)
            print(f"[preflight] {bin_msg}")
            if not ok_bin:
                return 1
        if args.launch:
            ok_scrub, scrub_msg = preflight_scrub_proxy(
                container_id, base_url=base_url or scrub_base_url(api_env)
            )
            print(f"[preflight] {scrub_msg}")
            if not ok_scrub:
                return 1
            ok_data, data_msg = preflight_dataset_volumes(
                container_id, sandbox.env, run_root=run_root
            )
            print(f"[preflight] {data_msg}")
            if not ok_data:
                return 1
            ok_skill, skill_msg = preflight_research_skills(run_root)
            print(f"[preflight] {skill_msg}")
            if not ok_skill:
                return 1

        readme = run_root / "README_BENCHMARK.md"
        resume_prompt = build_resume_continuation_prompt(task_dir)
        write_readme_benchmark(
            readme,
            run_root=run_root,
            container_id=container_id,
            docker_workdir=docker_workdir,
            config_path=config_path,
            provider=provider,
            model=model,
            prompt_path=prompt_path,
            thread_id=None,
            resume_prompt=resume_prompt,
        )

        if args.prepare_only:
            print(f"[prepare] done (no EvoSci launch). See {readme}")
            return 0

        if not args.launch:
            print(f"[prepare] sandbox ready; launch EvoSci manually. See {readme}")
            return 0

        if not evosci_bin or not api_key:
            print("EvoSci and API key are required for --launch.", file=sys.stderr)
            return 1

        env = build_container_env(
            api_env,
            agent_tool="evoscientist",
            run_root=run_root,
            task_env=sandbox.env,
            extra={BENCHMARK_AGENT_NATIVE_ENV: "1"},
        )
        (run_root / ".evoscientist").mkdir(parents=True, exist_ok=True)
        (run_root / ".container-home").mkdir(parents=True, exist_ok=True)
        log_path = run_root / "evoscientist_run.log"
        launch_prompt = prompt_path.read_text(encoding="utf-8").strip()
        resume_thread = getattr(args, "resume_thread", None)
        if resume_thread:
            launch_prompt = (args.resume_prompt or resume_prompt).strip()
            print(f"[prepare] resuming thread={resume_thread}")

        returncode = launch_evosci(
            container_id=container_id,
            evosci_bin=evosci_bin,
            run_root=run_root,
            env=env,
            log_path=log_path,
            prompt=launch_prompt,
            provider=provider,
            model=model,
            resume_thread=resume_thread,
            append_log=bool(resume_thread or existing_run),
        )
        if returncode != 0:
            print(
                f"[evoscientist] exited with code {returncode}. See {log_path}",
                file=sys.stderr,
            )

        thread_id = extract_thread_id_from_log(log_path) or resume_thread
        synced = sync_container_workspace_to_run_root(container_id, run_root)
        if synced:
            print(f"[sync] /workspace → run_root: {', '.join(synced)}")
        benchmark_complete, benchmark_issues = validate_run_deliverables(run_root, task_dir)

        max_resume_rounds = int(
            getattr(args, "max_auto_resume_rounds", DEFAULT_MAX_AUTO_RESUME_ROUNDS)
        )
        max_identical = int(
            getattr(args, "max_identical_resume_rounds", DEFAULT_MAX_IDENTICAL_RESUME_ROUNDS)
        )
        bg_wait_sec = float(getattr(args, "bg_wait_sec", DEFAULT_BG_WAIT_SEC))
        bg_poll_sec = float(getattr(args, "bg_poll_sec", DEFAULT_BG_POLL_SEC))
        auto_transient, max_transient = resolve_transient_retry_policy(args)
        resume_round = 0
        transient_round = 0
        identical_rounds = 0
        last_fp: tuple[str, ...] | None = None
        while True:
            exit_kind = classify_evosci_exit(log_path)
            bg_procs = list_background_experiment_procs(container_id)

            # 0) Background experiments still running → wait before any resume.
            if (
                not benchmark_complete
                and args.resume_on_incomplete
                and returncode == 0
                and (bg_procs or exit_kind.waiting)
            ):
                if bg_procs:
                    print(
                        f"[resume] detected {len(bg_procs)} background experiment proc(s); "
                        f"waiting up to {bg_wait_sec:.0f}s before continuation"
                    )
                    wait_for_background_experiments(
                        container_id,
                        poll_sec=bg_poll_sec,
                        max_wait_sec=bg_wait_sec,
                        log_path=log_path,
                    )
                synced = sync_container_workspace_to_run_root(container_id, run_root)
                if synced:
                    print(f"[sync] after bg wait: {', '.join(synced)}")
                benchmark_complete, benchmark_issues = validate_run_deliverables(
                    run_root, task_dir
                )
                if benchmark_complete:
                    break

            # 1) Incomplete deliverables / asking-user Goodbye after clean exit.
            if (
                not benchmark_complete
                and args.resume_on_incomplete
                and thread_id
                and returncode == 0
                and resume_round < max_resume_rounds
            ):
                fp = issues_fingerprint(benchmark_issues)
                if last_fp is not None and fp == last_fp:
                    identical_rounds += 1
                else:
                    identical_rounds = 0
                last_fp = fp
                if identical_rounds >= max_identical:
                    print(
                        f"[resume] stopping: validator issues unchanged for "
                        f"{identical_rounds} rounds ({'; '.join(benchmark_issues)})",
                        file=sys.stderr,
                    )
                    break

                resume_round += 1
                cont_prompt = build_hard_continuation_prompt(
                    run_root=run_root,
                    issues=benchmark_issues,
                    asking=exit_kind.asking,
                    waiting=exit_kind.waiting,
                    task_dir=task_dir,
                )
                why = []
                if exit_kind.asking:
                    why.append(f"asking:{exit_kind.matched!r}")
                if exit_kind.waiting:
                    why.append(f"waiting:{exit_kind.matched!r}")
                why.append("incomplete")
                print(
                    f"[validate] auto-resume {resume_round}/{max_resume_rounds} "
                    f"[{', '.join(why)}]:",
                    "; ".join(benchmark_issues),
                )
                resume_rc = launch_evosci(
                    container_id=container_id,
                    evosci_bin=evosci_bin,
                    run_root=run_root,
                    env=env,
                    log_path=log_path,
                    prompt=cont_prompt,
                    provider=provider,
                    model=model,
                    resume_thread=thread_id,
                    append_log=True,
                )
                if resume_rc != 0:
                    returncode = resume_rc
                else:
                    returncode = 0
                thread_id = extract_thread_id_from_log(log_path) or thread_id
                synced = sync_container_workspace_to_run_root(container_id, run_root)
                if synced:
                    print(f"[sync] after resume: {', '.join(synced)}")
                benchmark_complete, benchmark_issues = validate_run_deliverables(
                    run_root, task_dir
                )
                continue

            # 2) Transient upstream/agent crash (empty stream, 5xx, …).
            if returncode != 0 and auto_transient and transient_round < max_transient:
                probe = probe_transient_failure(returncode=returncode, log_path=log_path)
                if not probe.is_transient:
                    print(f"[retry] skip auto-resume ({probe.reason})", file=sys.stderr)
                    break
                transient_round += 1
                print(
                    f"[retry] transient failure ({probe.matched or probe.reason}); "
                    f"continuation {transient_round}/{max_transient}",
                    file=sys.stderr,
                )
                cont_prompt = build_hard_continuation_prompt(
                    run_root=run_root,
                    issues=benchmark_issues,
                    asking=False,
                    waiting=False,
                    task_dir=task_dir,
                )
                resume_rc = launch_evosci(
                    container_id=container_id,
                    evosci_bin=evosci_bin,
                    run_root=run_root,
                    env=env,
                    log_path=log_path,
                    prompt=cont_prompt,
                    provider=provider,
                    model=model,
                    resume_thread=thread_id,
                    append_log=True,
                )
                returncode = resume_rc
                thread_id = extract_thread_id_from_log(log_path) or thread_id
                synced = sync_container_workspace_to_run_root(container_id, run_root)
                if synced:
                    print(f"[sync] after transient retry: {', '.join(synced)}")
                benchmark_complete, benchmark_issues = validate_run_deliverables(
                    run_root, task_dir
                )
                continue

            break

        # Final sync before validate/manifest.
        synced = sync_container_workspace_to_run_root(container_id, run_root)
        if synced:
            print(f"[sync] final: {', '.join(synced)}")
        benchmark_complete, benchmark_issues = validate_run_deliverables(run_root, task_dir)

        write_readme_benchmark(
            readme,
            run_root=run_root,
            container_id=container_id,
            docker_workdir=docker_workdir,
            config_path=config_path,
            provider=provider,
            model=model,
            prompt_path=prompt_path,
            thread_id=thread_id,
            resume_prompt=resume_prompt,
        )

        if not benchmark_complete:
            print("[validate] benchmark incomplete:", "; ".join(benchmark_issues), file=sys.stderr)
            if returncode == 0:
                returncode = 2

        if args.evaluate:
            code, stdout, stderr = sandbox.evaluate()
            print(stdout.strip())
            if stderr.strip():
                print(stderr.strip(), file=sys.stderr)
            result_path = task_dir / "evaluator" / "results" / "result.json"
            if result_path.exists():
                print(
                    json.dumps(
                        json.loads(result_path.read_text(encoding="utf-8")),
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            if code != 0:
                returncode = code

        manifest = finalize_run_metadata(
            run_root,
            returncode=returncode,
            container_id=container_id,
            docker_workdir=docker_workdir,
            benchmark_complete=benchmark_complete,
            benchmark_issues=benchmark_issues,
            thread_id=thread_id,
        )
        print(f"[manifest] {manifest}")
        if benchmark_complete:
            print(f"Done. Run directory: {run_root}")
        else:
            print(
                f"Incomplete run. See {log_path} and resume via README_BENCHMARK.md. "
                f"Run directory: {run_root}",
                file=sys.stderr,
            )
        return returncode
    finally:
        destroy = args.cleanup or (args.launch and args.no_keep_sandbox)
        if destroy:
            print("[sandbox] cleaning up container...")
            sandbox.destroy()
        elif container_id:
            print(
                "[sandbox] container left running for manual session. "
                f"container_id={container_id}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare and optionally launch EvoScientist for a benchmark task "
            "(task.md → RESEARCH_BRIEF, Docker sandbox, workspace artifacts)."
        )
    )
    parser.add_argument("--task-dir", default=str(DEFAULT_TASK_DIR))
    parser.add_argument("--provider", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--no-keep-sandbox", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--no-resume-on-incomplete", action="store_true")
    parser.add_argument(
        "--max-auto-resume-rounds",
        type=int,
        default=DEFAULT_MAX_AUTO_RESUME_ROUNDS,
        help=(
            "When deliverables are incomplete after launch, resume the EvoSci thread "
            f"up to this many times (default {DEFAULT_MAX_AUTO_RESUME_ROUNDS})."
        ),
    )
    parser.add_argument(
        "--max-identical-resume-rounds",
        type=int,
        default=DEFAULT_MAX_IDENTICAL_RESUME_ROUNDS,
        help=(
            "Stop auto-resume after this many consecutive rounds with the same "
            f"validator issue fingerprint (default {DEFAULT_MAX_IDENTICAL_RESUME_ROUNDS})."
        ),
    )
    parser.add_argument(
        "--bg-wait-sec",
        type=float,
        default=DEFAULT_BG_WAIT_SEC,
        help="Max seconds to wait for background experiment processes before resuming.",
    )
    parser.add_argument(
        "--bg-poll-sec",
        type=float,
        default=DEFAULT_BG_POLL_SEC,
        help="Poll interval while waiting for background experiment processes.",
    )
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--resume-thread", default=None)
    parser.add_argument("--resume-prompt", default=None)
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Reuse an existing evoscientist_* run directory (continuation / resume).",
    )
    add_transient_retry_arguments(parser)
    args = parser.parse_args()

    task_dir = Path(args.task_dir).resolve()
    if not task_dir.is_dir():
        print(f"Task directory not found: {task_dir}", file=sys.stderr)
        return 1

    if not args.prepare_only and not args.launch:
        args.launch = True

    args.resume_on_incomplete = not args.no_resume_on_incomplete
    return run_pipeline(task_dir, args)


if __name__ == "__main__":
    raise SystemExit(main())
