#!/usr/bin/env python3
"""Run ARIS (ARIS-Code CLI + skills) on an ai_scientist_inputs benchmark task.

Prepares RESEARCH_BRIEF.md from task.md, installs ARIS skills into a run directory
under task_dir/workspace/, starts the benchmark Docker sandbox, and launches `aris`
inside the container with a `/research-pipeline` launch prompt.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS_ROOT = BENCHMARK_ROOT / "integrations"
ORCHESTRATOR_ROOT = BENCHMARK_ROOT / "orchestrator"
AI_SCIENTIST_ROOT = BENCHMARK_ROOT.parent / "AI-Scientist-v2"
DEFAULT_ARIS_REPO = Path.home() / "Auto-claude-code-research-in-sleep"
DEFAULT_TASK_DIR = (
    Path.home()
    / "ai_scientist_inputs/ASE-2025-004_predicting_recheck_success_in_continuous"
)

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
from aris_docker import (  # noqa: E402
    aris_process_env,
    containerize_aris_base_url,
    write_aris_runtime_config,
    write_aris_settings,
    write_benchmark_env,
)
from aris_task_layout import (  # noqa: E402
    finalize_run_metadata,
    prepare_run_layout,
    refresh_aligned_runtime_docs,
    validate_aris_deliverables,
    write_runtime_files,
)
from aris_workflow import build_aris_resume_continuation_prompt  # noqa: E402
from path_alignment import preflight_dataset_volumes  # noqa: E402
from sandbox import TaskSandbox  # noqa: E402
from seed_staging import shell_copy_agent_seeds  # noqa: E402
from benchmark_credentials import apply_benchmark_credentials, credentials_file_path, resolve_model  # noqa: E402
from transient_retry import (  # noqa: E402
    add_transient_retry_arguments,
    probe_transient_failure,
    resolve_existing_run_dir,
    resolve_transient_retry_policy,
)


def resolve_aris_repo(explicit: str | None) -> Path:
    for candidate in (explicit, os.environ.get("ARIS_REPO"), str(DEFAULT_ARIS_REPO)):
        if candidate:
            repo = Path(candidate).resolve()
            if (repo / "tools" / "install_aris.sh").is_file():
                return repo
    raise FileNotFoundError(
        "Could not locate Auto-claude-code-research-in-sleep repo "
        f"(expected install_aris.sh under {DEFAULT_ARIS_REPO})"
    )



def load_aris_runtime_config(host_env: dict[str, str]) -> tuple[dict[str, object], str]:
    """Build ARIS config.json payload and executor model for in-container launch."""
    merged = apply_benchmark_credentials(host_env)

    host_cfg_path = Path.home() / ".config" / "aris" / "config.json"
    host_cfg: dict[str, object] = {}
    if host_cfg_path.is_file():
        try:
            loaded = json.loads(host_cfg_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                host_cfg = loaded
        except json.JSONDecodeError:
            host_cfg = {}

    api_key = str(
        host_cfg.get("executor_api_key")
        or merged.get("EXECUTOR_API_KEY")
        or merged.get("CUSTOM_OPENAI_API_KEY")
        or merged.get("OPENAI_API_KEY")
        or ""
    ).strip()
    if not api_key:
        raise RuntimeError(
            "Missing API key for ARIS. Set llm.api_key in "
            f"{credentials_file_path()} (or run: python3 integrations/benchmark_credentials.py --init)."
        )

    base_url = containerize_aris_base_url(
        str(host_cfg.get("executor_base_url") or merged.get("EXECUTOR_BASE_URL") or scrub_base_url(merged)),
        merged,
    )
    model = str(
        host_cfg.get("executor_model")
        or resolve_model("aris", role="executor", env=merged)
    ).strip()
    if model.startswith("openai/"):
        model = model.split("/", 1)[1]

    reviewer_provider = str(host_cfg.get("reviewer_provider") or "custom")
    reviewer_key = str(host_cfg.get("reviewer_api_key") or api_key).strip()
    reviewer_base = containerize_aris_base_url(
        str(host_cfg.get("reviewer_base_url") or base_url),
        merged,
    )
    reviewer_model = str(
        host_cfg.get("reviewer_model")
        or resolve_model("aris", role="reviewer", env=merged)
    ).strip()

    config: dict[str, object] = {
        "executor_provider": str(host_cfg.get("executor_provider") or "custom"),
        "executor_api_key": api_key,
        "executor_base_url": base_url,
        "executor_model": model,
        "reviewer_provider": reviewer_provider,
        "reviewer_api_key": reviewer_key,
        "reviewer_base_url": reviewer_base,
        "reviewer_model": reviewer_model,
        "reviewer_fallback_provider": host_cfg.get("reviewer_fallback_provider"),
        "language": str(host_cfg.get("language") or merged.get("ARIS_LANGUAGE") or "en"),
        "meta_logging": host_cfg.get("meta_logging"),
    }
    return config, model


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


def build_aris_command(aris_bin: str, prompt_path: Path, *, model: str | None = None) -> list[str]:
    prompt = prompt_path.read_text(encoding="utf-8").strip()
    cmd = [
        aris_bin,
        "--dangerously-skip-permissions",
        "--permission-mode",
        "danger-full-access",
        "--output-format",
        "text",
    ]
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)
    return cmd


def run_pipeline(task_dir: Path, args: argparse.Namespace) -> int:
    if not shutil.which("docker"):
        print("docker is required for ARIS benchmark experiment isolation.", file=sys.stderr)
        return 1

    try:
        aris_repo = resolve_aris_repo(args.aris_repo)
        aris_bin = resolve_binary("aris", "aris", os.environ)
        aris_config, aris_model = load_aris_runtime_config(os.environ)
    except (FileNotFoundError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        existing_run = resolve_existing_run_dir(getattr(args, "run_dir", None))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    run_root, workspace_root = prepare_run_layout(
        task_dir,
        aris_repo=aris_repo,
        install_skills=not args.skip_skill_install,
        run_dir=existing_run,
    )
    if existing_run is not None:
        print(f"[prepare] reusing run_dir={run_root}")
    docker_workdir = workdir_for_run(run_root)
    print(f"[prepare] run_root={run_root}")

    from agent_container import apply_run_metering_to_env

    metered_env = apply_run_metering_to_env(os.environ.copy(), run_root=run_root, for_container=True)
    metered_base = (
        metered_env.get("OPENAI_BASE_URL")
        or metered_env.get("OPENAI_API_BASE")
        or ""
    ).rstrip("/")
    if metered_base:
        aris_config["executor_base_url"] = metered_base
        aris_config["reviewer_base_url"] = metered_base
        print(f"[prepare] metering_base_url={metered_base}")

    sandbox = TaskSandbox(task_dir, agent_tool="aris")
    container_id: str | None = None
    returncode = 0

    try:
        container_id = sandbox.start(agent_tool="aris", run_root=run_root)
        print(f"[sandbox] container_id={container_id}")
        print(f"[sandbox] workdir={docker_workdir}")

        write_benchmark_env(
            run_root,
            container_id=container_id,
            docker_workdir=docker_workdir,
            host_run_root=run_root,
        )
        settings_path = write_aris_settings(run_root)
        aris_config_path = write_aris_runtime_config(run_root, aris_config)
        print(f"[prepare] aris_config={aris_config_path}")
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
        ok_bin, bin_msg = preflight_binary(container_id, aris_bin, cwd=run_root)
        print(f"[preflight] {bin_msg}")
        if not ok_bin:
            return 1
        if args.launch:
            executor_base = str(aris_config.get("executor_base_url") or "")
            if "host.docker.internal" in executor_base or "127.0.0.1" in executor_base or "localhost" in executor_base:
                ok_scrub, scrub_msg = preflight_scrub_proxy(container_id, base_url=executor_base)
                print(f"[preflight] {scrub_msg}")
                if not ok_scrub:
                    return 1
            ok_data, data_msg = preflight_dataset_volumes(
                container_id, sandbox.env, run_root=run_root
            )
            print(f"[preflight] {data_msg}")
            if not ok_data:
                return 1

        readme = run_root / "README_BENCHMARK.md"
        readme.write_text(
            "\n".join(
                [
                    "# ARIS benchmark run",
                    "",
                    f"- Prepared: {datetime.now().isoformat(timespec='seconds')}",
                    f"- Container: `{container_id}`",
                    f"- Workdir: `{docker_workdir}`",
                    f"- Execution: in-container (aligned paths)",
                    f"- ARIS settings: `{settings_path}`",
                    "",
                    "## Manual launch",
                    "",
                    "Resume an interrupted run inside the container with",
                    "`/research-pipeline — resume <run_id>` (see `.aris/runs/`).",
                    "",
                    "```bash",
                    f"python3 {BENCHMARK_ROOT / 'integrations' / 'run_aris_task.py'} \\",
                    f"  --task-dir {task_dir} --launch --run-dir {run_root}",
                    "```",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        if args.prepare_only:
            print(f"[prepare] done (no ARIS launch). See {readme}")
            return 0

        if not args.launch:
            print(f"[prepare] sandbox ready; launch ARIS manually. See {readme}")
            return 0

        aris_env = aris_process_env(aris_config)
        env = build_container_env(
            os.environ,
            agent_tool="aris",
            run_root=run_root,
            task_env=sandbox.env,
            extra={BENCHMARK_AGENT_NATIVE_ENV: "1", **aris_env},
        )
        log_path = run_root / "aris_run.log"
        # Fresh launch uses the prepared research-pipeline prompt; continuations overwrite.
        if existing_run is not None:
            cont = build_aris_resume_continuation_prompt(task_dir, run_root)
            prompt_path = run_root / ".aris-benchmark" / "continuation_prompt.txt"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(cont, encoding="utf-8")
            print(f"[prepare] continuation prompt for --run-dir: {prompt_path}")

        cmd = build_aris_command(aris_bin, prompt_path, model=aris_model)
        print("[launch] in-container:", " ".join(cmd[:6]), "<prompt...>")
        print(f"[launch] log={log_path}")

        with log_path.open("a" if existing_run else "w", encoding="utf-8") as log_file:
            label = "resume" if existing_run else "launch"
            log_file.write(f"\n# ARIS {label} {datetime.now().isoformat(timespec='seconds')}\n")
            log_file.write(f"# cwd={run_root}\n")
            log_file.write(f"# container={container_id}\n\n")

        returncode = launch_agent(
            container_id=container_id,
            cmd=cmd,
            cwd=run_root,
            env=env,
            log_path=log_path,
            append=True,
        )
        if returncode != 0:
            print(f"[aris] exited with code {returncode}. See {log_path}", file=sys.stderr)

        auto_resume, max_rounds = resolve_transient_retry_policy(args)
        resume_round = 0
        while returncode != 0 and auto_resume and resume_round < max_rounds:
            probe = probe_transient_failure(returncode=returncode, log_path=log_path)
            if not probe.is_transient:
                print(f"[retry] skip auto-resume ({probe.reason})", file=sys.stderr)
                break
            resume_round += 1
            print(
                f"[retry] transient failure detected ({probe.matched or probe.reason}); "
                f"continuation {resume_round}/{max_rounds} in {run_root}",
                file=sys.stderr,
            )
            cont = build_aris_resume_continuation_prompt(task_dir, run_root)
            cont_path = run_root / ".aris-benchmark" / "continuation_prompt.txt"
            cont_path.write_text(cont, encoding="utf-8")
            cont_cmd = build_aris_command(aris_bin, cont_path, model=aris_model)
            with log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(
                    f"\n\n# ARIS auto-continuation {resume_round}/{max_rounds} "
                    f"{datetime.now().isoformat(timespec='seconds')}\n"
                    f"# reason={probe.reason}\n\n"
                )
            returncode = launch_agent(
                container_id=container_id,
                cmd=cont_cmd,
                cwd=run_root,
                env=env,
                log_path=log_path,
                append=True,
            )
            if returncode != 0:
                print(
                    f"[aris] continuation exited with code {returncode}. See {log_path}",
                    file=sys.stderr,
                )

        validation_issues: list[str] = []
        if args.launch and not args.prepare_only:
            complete, validation_issues = validate_aris_deliverables(run_root, task_dir)
            if not complete:
                for issue in validation_issues:
                    print(f"[validate] {issue}", file=sys.stderr)
                if returncode == 0:
                    returncode = 1
            else:
                print("[validate] benchmark deliverables OK")

        if args.evaluate:
            code, stdout, stderr = sandbox.evaluate()
            print(stdout.strip())
            if stderr.strip():
                print(stderr.strip(), file=sys.stderr)
            result_path = task_dir / "evaluator" / "results" / "result.json"
            if result_path.exists():
                print(json.dumps(json.loads(result_path.read_text(encoding="utf-8")), indent=2, ensure_ascii=False))
            if code != 0:
                returncode = code

        manifest = finalize_run_metadata(
            run_root,
            returncode=returncode,
            container_id=container_id,
            docker_workdir=docker_workdir,
            validation_issues=validation_issues,
        )
        print(f"[manifest] {manifest}")
        print(f"Done. Run directory: {run_root}")
        return returncode
    finally:
        if args.cleanup or (args.launch and not args.keep_sandbox):
            print("[sandbox] cleaning up container...")
            sandbox.destroy()
        elif container_id:
            print(
                "[sandbox] container left running for manual ARIS session. "
                f"container_id={container_id}"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and optionally launch ARIS /research-pipeline for a benchmark task."
    )
    parser.add_argument("--task-dir", default=str(DEFAULT_TASK_DIR))
    parser.add_argument("--aris-repo", default=None)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--launch", action="store_true")
    parser.add_argument("--skip-skill-install", action="store_true")
    parser.add_argument("--keep-sandbox", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Reuse an existing aris_* run directory (continuation / manual resume).",
    )
    add_transient_retry_arguments(parser)
    args = parser.parse_args()

    task_dir = Path(args.task_dir).resolve()
    if not task_dir.is_dir():
        print(f"Task directory not found: {task_dir}", file=sys.stderr)
        return 1

    if not args.prepare_only and not args.launch:
        args.launch = True

    return run_pipeline(task_dir, args)


if __name__ == "__main__":
    raise SystemExit(main())
