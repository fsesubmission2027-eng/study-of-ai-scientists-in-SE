#!/usr/bin/env python3
"""Run AI-Researcher on an ai_scientist_inputs task via TaskSandbox (in-container).

Aligns with other benchmark tools:

- ``--task-dir`` any ``ai_scientist_inputs/<TASK>/`` package
- synthesizes AI-Researcher instance JSON from ``task.md`` + ``related_work.json``
- timestamped ``workspace/airesearcher_<ts>/`` run root (or ``--run-dir`` resume)
- Docker via shared ``TaskSandbox`` + in-container native InnoFlow
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

AI_RESEARCHER_ROOT = Path.home() / "AI-Researcher"
BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS_ROOT = BENCHMARK_ROOT / "integrations"
RESEARCH_AGENT_ROOT = AI_RESEARCHER_ROOT / "research_agent"
ORCHESTRATOR_ROOT = BENCHMARK_ROOT / "orchestrator"
DEFAULT_TASK_DIR = (
    Path.home()
    / "ai_scientist_inputs/ASE-2025-013_automated_decomposition_of_large_header"
)

# AI-Researcher root provides ``global_state`` and the ``research_agent`` package;
# research_agent/ remains for legacy bare ``import inno`` / ``import constant``.
sys.path.insert(0, str(ORCHESTRATOR_ROOT))
sys.path.insert(0, str(INTEGRATIONS_ROOT))
sys.path.insert(0, str(RESEARCH_AGENT_ROOT))
sys.path.insert(0, str(AI_RESEARCHER_ROOT))

from agent_container import (  # noqa: E402
    BENCHMARK_AGENT_NATIVE_ENV,
    BENCHMARK_RUN_ROOT_ENV,
    build_container_env,
    launch_agent,
    load_api_env,
    preflight_path,
    preflight_python,
    preflight_runtime_mounts,
    preflight_scrub_proxy,
    print_log_tail,
    workdir_for_run,
)
from airesearcher_docker import ensure_playwright_system_deps, write_benchmark_env  # noqa: E402
from airesearcher_env import build_env, setup_dataset  # noqa: E402
from airesearcher_literature_seed import warp_source_papers  # noqa: E402
from airesearcher_metaprompt import install_task_metaprompt  # noqa: E402
from airesearcher_no_progress import install_no_progress_breaker  # noqa: E402
from airesearcher_task_layout import (  # noqa: E402
    apply_writable_home_env,
    build_task2_prompt,
    finalize_run_metadata,
    prepare_run_layout,
    write_instance_files,
)
from agent_task_document import build_agent_task_document  # noqa: E402
from path_alignment import load_task_env, preflight_dataset_volumes  # noqa: E402
from benchmark_credentials import apply_benchmark_credentials, credentials_file_path  # noqa: E402
from researchclaw_literature_seed import RelatedWorkError  # noqa: E402
from sandbox import TaskSandbox  # noqa: E402
from seed_staging import shell_copy_agent_seeds  # noqa: E402
from transient_retry import (  # noqa: E402
    add_transient_retry_arguments,
    resolve_existing_run_dir,
    retry_launch_on_transient,
)


def _load_instance(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Instance JSON must be an object: {path}")
    return data


def resolve_instance_path(
    run_root: Path,
    *,
    explicit: Path | None = None,
    category: str | None = None,
    instance_id: str | None = None,
) -> Path:
    if explicit is not None:
        path = explicit.expanduser()
        if not path.is_absolute():
            path = (run_root / path).resolve()
        else:
            path = path.resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Missing instance JSON: {path}")
        return path

    generated = run_root / ".airesearcher-benchmark" / "instance.json"
    if generated.is_file():
        return generated

    if category and instance_id:
        legacy = AI_RESEARCHER_ROOT / "benchmark" / "final" / category / f"{instance_id}.json"
        if legacy.is_file():
            return legacy
        raise FileNotFoundError(f"Missing benchmark instance: {legacy}")

    raise FileNotFoundError(
        f"No AI-Researcher instance at {generated}. "
        "Run prepare_run_layout first, or pass --instance-json / --category+--instance-id."
    )


def run_native_flow(args: argparse.Namespace) -> int:
    merged = apply_benchmark_credentials(os.environ)
    os.environ.update(merged)
    os.environ["PYTHONPATH"] = airesearcher_pythonpath()
    # Keep sys.path in sync for this process (container may have restarted with a fresh interpreter).
    for path in (
        str(AI_RESEARCHER_ROOT),
        str(RESEARCH_AGENT_ROOT),
        str(INTEGRATIONS_ROOT),
        str(ORCHESTRATOR_ROOT),
    ):
        if path not in sys.path:
            sys.path.insert(0, path)

    task_dir = Path(args.task_dir).resolve()
    run_root_raw = (os.environ.get(BENCHMARK_RUN_ROOT_ENV) or "").strip()
    if args.run_dir:
        run_root = Path(args.run_dir).expanduser().resolve()
    elif run_root_raw:
        run_root = Path(run_root_raw).resolve()
    else:
        run_root = (task_dir / "workspace").resolve()
    run_root.mkdir(parents=True, exist_ok=True)
    os.environ[BENCHMARK_RUN_ROOT_ENV] = str(run_root)

    explicit_instance = Path(args.instance_json) if args.instance_json else None
    try:
        instance_path = resolve_instance_path(
            run_root,
            explicit=explicit_instance,
            category=args.category if args.category != "benchmark" else None,
            instance_id=args.instance_id or None,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    eval_instance = _load_instance(instance_path)
    source_papers = list(eval_instance.get("source_papers") or [])
    if not source_papers:
        print(f"Instance has empty source_papers: {instance_path}", file=sys.stderr)
        return 1

    task_env = load_task_env(task_dir)
    if args.task_level == "task1":
        ideas = str(eval_instance.get("task1") or "").strip() or build_agent_task_document(
            task_dir, task_env
        )
    else:
        ideas = str(eval_instance.get("task2") or "").strip() or build_task2_prompt(task_dir)

    references = warp_source_papers(source_papers)
    category = str(
        args.category
        or eval_instance.get("category")
        or "benchmark"
    )
    instance_id = str(
        args.instance_id
        or eval_instance.get("instance_id")
        or run_root.name
    )

    os.chdir(run_root)
    # Host /home is not fully mounted in the sandbox; redirect HOME/XDG cache first.
    apply_writable_home_env(run_root, os.environ)
    # RequestsMarkdownBrowser (imported via terminal_tools) opens chromadb at
    # ``./paper_db`` relative to cwd — must be a writable path (run_root), not the
    # AI-Researcher install tree when that mount is read-only.

    # FlowCache prompts via inquirer when cache files exist; docker has no TTY.
    import research_agent.inno.util as _airesearcher_util

    def _noninteractive_select_menu(options, message: str = ""):
        preferred = (os.environ.get("AIRESEARCHER_CACHE_CHOICE") or "Yes").strip()
        if preferred in options:
            choice = preferred
        else:
            for pref in ("Yes", "Resume", "No"):
                if pref in options:
                    choice = pref
                    break
            else:
                choice = options[0]
        print(f"[airesearcher] cache prompt (non-interactive): {message} -> {choice}")
        return choice

    _airesearcher_util.single_select_menu = _noninteractive_select_menu

    from research_agent.constant import COMPLETION_MODEL
    from research_agent.inno.environment.browser_env import BrowserEnv
    from research_agent.inno.environment.markdown_browser import RequestsMarkdownBrowser
    import research_agent.inno.core as _airesearcher_core
    import research_agent.inno.tools.inno_tools.code_search as _code_search
    import research_agent.run_infer_plan as _run_infer_plan
    from research_agent.run_infer_plan import InnoFlow
    from tqdm import tqdm

    # DeepSeek V4 defaults to thinking mode and rejects tool_choice=required/object.
    # Upstream AI-Researcher agents hardcode tool_choice="required" (designed for GPT).
    # Integration chose openai/deepseek-v4-* via credentials — adapt at the litellm call site
    # (do not edit AI-Researcher agent sources).
    def _needs_deepseek_v4_tool_compat(model: str) -> bool:
        name = (model or "").lower()
        return "deepseek-v4" in name or "deepseek-reasoner" in name

    def _deepseek_v4_compat_kwargs(kwargs: dict) -> dict:
        out = dict(kwargs)
        model = str(out.get("model") or "")
        if not _needs_deepseek_v4_tool_compat(model):
            return out
        tool_choice = out.get("tool_choice")
        if tool_choice in ("required", "any") or isinstance(tool_choice, dict):
            print(
                f"[airesearcher] remap tool_choice={tool_choice!r} -> 'auto' "
                f"for thinking-mode model {model}",
                flush=True,
            )
            out["tool_choice"] = "auto"
        # Prefer non-thinking so MetaChain tool loops need not round-trip reasoning_content.
        extra = dict(out.get("extra_body") or {})
        if "thinking" not in extra:
            extra["thinking"] = {"type": "disabled"}
            out["extra_body"] = extra
            print(
                f"[airesearcher] disable thinking mode for {model} "
                "(upstream tool loop is not reasoner-aware)",
                flush=True,
            )
        return out

    _orig_completion = _airesearcher_core.completion
    _orig_acompletion = _airesearcher_core.acompletion

    def _compat_completion(**kwargs):
        return _orig_completion(**_deepseek_v4_compat_kwargs(kwargs))

    async def _compat_acompletion(**kwargs):
        return await _orig_acompletion(**_deepseek_v4_compat_kwargs(kwargs))

    _airesearcher_core.completion = _compat_completion
    _airesearcher_core.acompletion = _compat_acompletion

    # A tool that raises the same error every call (e.g. upstream case_resolved
    # KeyError) is retried forever by MetaChain, each retry costing a full LLM
    # round trip. Stop the turn after N identical failures instead.
    install_no_progress_breaker(_airesearcher_core)

    # Upstream github_search hits GitHub once per source paper.
    # Cap papers only (default 10 ≈ upstream median); keep per-query repo limit as upstream (10).
    # Soft-fail 403 so one rate-limit does not abort the whole pipeline.
    # Patches are applied in-process only — AI-Researcher source tree is not modified.
    _gh_paper_limit = max(1, int(os.environ.get("AIRESEARCHER_GITHUB_PAPER_LIMIT", "10")))
    _orig_search_github_repos = _code_search.search_github_repos

    def _soft_search_github_repos(context_variables, query, limit=10):
        try:
            return _orig_search_github_repos(context_variables, query, limit)
        except Exception as exc:  # noqa: BLE001 — upstream raises bare Exception on 403
            text = str(exc)
            if "403" in text or "rate limit" in text.lower():
                print(
                    f"[airesearcher] GitHub search skipped (rate limit) for: {str(query)[:100]}",
                    flush=True,
                )
                return (
                    f"The results of searching {query} on GitHub: \n"
                    "(skipped: GitHub API rate limit exceeded)\n"
                )
            raise

    def _capped_github_search(metadata: dict) -> str:
        all_papers = list(metadata.get("source_papers") or [])
        papers = all_papers[:_gh_paper_limit]
        print(
            f"[airesearcher] GitHub search over {len(papers)}/{len(all_papers)} "
            f"papers (limit={_gh_paper_limit}, repos/query=upstream default)",
            flush=True,
        )
        github_result = ""
        for source_paper in tqdm(papers):
            # Match upstream github_search(..., 10).
            github_result += _soft_search_github_repos(
                metadata, source_paper["reference"], 10
            )
            github_result += "*" * 30 + "\n"
        return github_result

    _code_search.search_github_repos = _soft_search_github_repos
    _run_infer_plan.search_github_repos = _soft_search_github_repos
    _run_infer_plan.github_search = _capped_github_search

    # Upstream imports benchmark.process.dataset_candidate.<category>.metaprompt
    # after survey. Official categories are ML-only; synthesize from task.md/seeds
    # for every integration run (works for SE / synthetic-data tasks too).
    install_task_metaprompt(
        category=category,
        task_dir=task_dir,
        run_root=run_root,
        force=True,
    )

    code_env = build_env(task_dir, native=True, run_root=run_root)
    # BrowserEnv / RequestsMarkdownBrowser join local_root / workplace_name → run_root.
    local_root = str(run_root.parent)
    workplace_name = run_root.name
    flow_workplace_name = str(run_root)

    try:
        code_env.init_container()
        setup_dataset(category, code_env.local_workplace, task_dir=task_dir)

        web_env = BrowserEnv(
            browsergym_eval_env=None,
            local_root=local_root,
            workplace_name=workplace_name,
        )
        file_env = RequestsMarkdownBrowser(
            viewport_size=1024 * 4,
            local_root=local_root,
            workplace_name=workplace_name,
            downloads_folder=os.path.join(code_env.local_workplace, "downloads"),
        )

        cache_suffix = f"{instance_id}_{COMPLETION_MODEL.replace('/', '__')}"
        flow = InnoFlow(
            cache_path=f"cache_{cache_suffix}",
            log_path=f"log_{instance_id}",
            code_env=code_env,
            web_env=web_env,
            file_env=file_env,
            model=COMPLETION_MODEL,
        )
        # Ensure the constructed flow uses the capped/soft-fail GitHub search.
        from research_agent.inno.workflow.flowcache import ToolModule

        flow.git_search = ToolModule(_capped_github_search, flow.git_search.cache_path)

        asyncio.run(
            flow(
                instance_path=str(instance_path),
                task_level=args.task_level,
                local_root=code_env.local_workplace,
                workplace_name=flow_workplace_name,
                max_iter_times=args.max_iter_times,
                category=category,
                ideas=ideas,
                references=references,
            )
        )
    finally:
        code_env.stop_container()

    print(f"Done. Artifacts: {run_root}")
    return 0


def airesearcher_pythonpath() -> str:
    """Host/container PYTHONPATH so ``global_state`` + ``research_agent`` resolve."""
    parts = [
        str(AI_RESEARCHER_ROOT),
        str(RESEARCH_AGENT_ROOT),
        str(INTEGRATIONS_ROOT),
        str(ORCHESTRATOR_ROOT),
    ]
    existing = (os.environ.get("PYTHONPATH") or "").strip()
    if existing:
        parts.append(existing)
    # Preserve order, drop empties / dupes.
    seen: set[str] = set()
    ordered: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.add(part)
            ordered.append(part)
    return ":".join(ordered)


def resolve_airesearcher_python(container_id: str, *, cwd: Path) -> str:
    from agent_container import preflight_binary

    # Prefer the project venv (has litellm / browsergym / …); it symlinks into
    # ~/.local/share/uv which is mounted for the airesearcher agent tool.
    for candidate in (
        str(AI_RESEARCHER_ROOT / ".venv" / "bin" / "python"),
        str(AI_RESEARCHER_ROOT / ".venv" / "bin" / "python3"),
        str(Path.home() / "miniconda3/bin/python3"),
        "python3",
    ):
        ok, _msg = preflight_binary(container_id, candidate, cwd=cwd)
        if ok:
            return candidate
    return "python3"


def run_container_preflight(container_id: str, *, workspace: Path, python_bin: str) -> bool:
    from agent_container import preflight_python_import

    ok_mounts, mount_issues = preflight_runtime_mounts(
        container_id, "airesearcher", cwd=workspace
    )
    for issue in mount_issues:
        print(f"[preflight] mount: {issue}", file=sys.stderr)
    if not ok_mounts:
        return False

    ok_scrub, scrub_msg = preflight_scrub_proxy(container_id)
    print(f"[preflight] {scrub_msg}")
    if not ok_scrub:
        return False

    script = BENCHMARK_ROOT / "integrations" / "run_airesearcher_task.py"
    ok_script, script_msg = preflight_path(container_id, str(script), cwd=workspace)
    print(f"[preflight] {script_msg}")
    if not ok_script:
        return False

    ok_repo, repo_msg = preflight_path(
        container_id,
        str(AI_RESEARCHER_ROOT),
        cwd=workspace,
        must_be_dir=True,
    )
    print(f"[preflight] {repo_msg}")
    if not ok_repo:
        return False

    # Catch missing global_state / litellm / tool registry before a long agent launch.
    # terminal_tools opens chromadb + tiktoken caches under HOME/.cache — use run HOME.
    home = workspace.resolve() / ".container-home"
    cache = home / ".cache"
    home.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    playwright = Path.home() / ".cache" / "ms-playwright"
    playwright_line = (
        f"os.environ['PLAYWRIGHT_BROWSERS_PATH']={str(playwright)!r}; "
        if playwright.is_dir()
        else ""
    )
    import_stmt = (
        "import os, sys; "
        f"os.chdir({str(workspace.resolve())!r}); "
        f"os.environ['HOME']={str(home)!r}; "
        f"os.environ['XDG_CACHE_HOME']={str(cache)!r}; "
        f"{playwright_line}"
        f"sys.path[:0]=[{str(AI_RESEARCHER_ROOT)!r}, {str(RESEARCH_AGENT_ROOT)!r}]; "
        "import global_state, research_agent.constant, litellm; "
        "from research_agent.inno.tools import gen_code_tree_structure; "
        "print('airesearcher-imports-ok')"
    )
    ok_imp, imp_msg = preflight_python_import(
        container_id,
        python_bin=python_bin,
        import_stmt=import_stmt,
        cwd=workspace,
    )
    print(f"[preflight] {imp_msg}")
    return ok_imp


def seed_container_workspace(sandbox: TaskSandbox, run_root: Path) -> None:
    from path_alignment import align_run_dataset_paths

    seeds_path = sandbox.seeds_path()
    req = f"{seeds_path}/requirements.txt"
    seeds_dir = sandbox.task_dir / "seeds"
    copy_cmd = shell_copy_agent_seeds(seeds_dir, f"{run_root}/dataset_candidate")
    sandbox.exec(
        f"mkdir -p {run_root}/dataset_candidate "
        f"{run_root}/project {run_root}/results {run_root}/paper "
        f"{run_root}/downloads && {copy_cmd}",
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


def run_pipeline(task_dir: Path, args: argparse.Namespace) -> int:
    if not shutil.which("docker"):
        print("docker is required for AI-Researcher benchmark runs.", file=sys.stderr)
        return 1

    host_env = os.environ.copy()
    if not load_api_env(host_env, env_file=Path.home() / "AI-Scientist-v2" / ".env"):
        # Still allow prepare-only without keys.
        if args.launch and not args.prepare_only:
            print(
                f"Missing OPENAI_API_KEY. Set llm.api_key in {credentials_file_path()} "
                "(or run: python3 integrations/benchmark_credentials.py --init)",
                file=sys.stderr,
            )
            return 1

    try:
        existing_run = resolve_existing_run_dir(getattr(args, "run_dir", None))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    related_work = Path(args.related_work) if args.related_work else None
    try:
        run_root, _workspace_root, instance_path, warnings = prepare_run_layout(
            task_dir,
            run_dir=existing_run,
            related_work_path=related_work,
            instance_id=args.instance_id or None,
            category=args.category,
            require_literature=not bool(args.instance_json),
        )
    except RelatedWorkError as exc:
        # Optional legacy instance path under AI-Researcher/benchmark/final.
        if args.category != "benchmark" and args.instance_id:
            legacy = (
                AI_RESEARCHER_ROOT
                / "benchmark"
                / "final"
                / args.category
                / f"{args.instance_id}.json"
            )
            if not legacy.is_file():
                print(str(exc), file=sys.stderr)
                return 1
            from airesearcher_task_layout import seed_run_workspace

            task_env = load_task_env(task_dir)
            if existing_run is not None:
                run_root = existing_run
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                run_root = task_dir / "workspace" / f"airesearcher_{timestamp}"
                run_root.mkdir(parents=True, exist_ok=True)
            brief = build_agent_task_document(task_dir, task_env)
            (run_root / "RESEARCH_BRIEF.md").write_text(brief, encoding="utf-8")
            (run_root / "task_input.md").write_text(brief, encoding="utf-8")
            seed_run_workspace(run_root, task_dir, task_env)
            eval_instance = _load_instance(legacy)
            instance_path, _ = write_instance_files(run_root, eval_instance)
            warnings = [f"using legacy instance {legacy}"]
        elif args.instance_json:
            from airesearcher_task_layout import seed_run_workspace

            task_env = load_task_env(task_dir)
            if existing_run is not None:
                run_root = existing_run
            else:
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                run_root = task_dir / "workspace" / f"airesearcher_{timestamp}"
                run_root.mkdir(parents=True, exist_ok=True)
            brief = build_agent_task_document(task_dir, task_env)
            (run_root / "RESEARCH_BRIEF.md").write_text(brief, encoding="utf-8")
            (run_root / "task_input.md").write_text(brief, encoding="utf-8")
            seed_run_workspace(run_root, task_dir, task_env)
            eval_instance = _load_instance(Path(args.instance_json).expanduser().resolve())
            instance_path, _ = write_instance_files(run_root, eval_instance)
            warnings = [f"using --instance-json {args.instance_json}"]
        else:
            print(str(exc), file=sys.stderr)
            return 1

    for warning in warnings:
        print(f"[prepare] {warning}")
    if existing_run is not None:
        print(f"[prepare] reusing run_dir={run_root}")
    docker_workdir = workdir_for_run(run_root)
    print(f"[prepare] run_root={run_root}")
    print(f"[prepare] instance={instance_path}")

    sandbox = TaskSandbox(task_dir, agent_tool="airesearcher")
    container_id: str | None = None
    returncode = 0
    log_path = run_root / "airesearcher_run.log"
    destroy_sandbox = True

    try:
        container_id = sandbox.start(agent_tool="airesearcher", run_root=run_root)
        print(f"[sandbox] container_id={container_id}")
        print(f"[sandbox] workdir={docker_workdir}")

        ok_pw, pw_msg = ensure_playwright_system_deps(container_id)
        print(f"[preflight] {pw_msg}")
        if not ok_pw:
            return 1

        write_benchmark_env(
            run_root,
            container_id=container_id,
            docker_workdir=docker_workdir,
            host_run_root=run_root,
            instance_path=instance_path,
        )
        seed_container_workspace(sandbox, run_root)

        ok, preflight_msg = preflight_python(container_id, run_root)
        print(f"[preflight] {preflight_msg}")
        if not ok:
            return 1

        python_bin = resolve_airesearcher_python(container_id, cwd=run_root)
        print(f"[preflight] python={python_bin}")
        if not run_container_preflight(container_id, workspace=run_root, python_bin=python_bin):
            return 1

        if args.launch:
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
                    "# AI-Researcher benchmark run",
                    "",
                    f"- Prepared: {datetime.now().isoformat(timespec='seconds')}",
                    f"- Container: `{container_id}`",
                    f"- Workdir: `{docker_workdir}`",
                    f"- Instance: `{instance_path}`",
                    f"- Execution: in-container (aligned paths)",
                    "",
                    "## Manual launch",
                    "",
                    "```bash",
                    f"python3 {BENCHMARK_ROOT / 'integrations' / 'run_airesearcher_task.py'} \\",
                    f"  --task-dir {task_dir} --launch --run-dir {run_root}",
                    "```",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        if args.prepare_only or not args.launch:
            # Keep sandbox for manual attach unless --cleanup.
            destroy_sandbox = bool(args.cleanup)
            print(f"[prepare] done (no AI-Researcher launch). See {readme}")
            return 0

        env = build_container_env(
            host_env,
            agent_tool="airesearcher",
            run_root=run_root,
            task_env=sandbox.env,
            extra={
                BENCHMARK_AGENT_NATIVE_ENV: "1",
                BENCHMARK_RUN_ROOT_ENV: str(run_root),
                "AIRESEARCHER_INSTANCE_PATH": str(instance_path),
                "PYTHONPATH": airesearcher_pythonpath(),
                "VIRTUAL_ENV": str(AI_RESEARCHER_ROOT / ".venv"),
                # FlowCache inquirer prompts need a default when stdin is not a TTY.
                "AIRESEARCHER_CACHE_CHOICE": os.environ.get("AIRESEARCHER_CACHE_CHOICE", "Yes"),
            },
        )
        script = str(BENCHMARK_ROOT / "integrations" / "run_airesearcher_task.py")
        cmd = [
            python_bin,
            script,
            "--native",
            "--task-dir",
            str(task_dir),
            "--run-dir",
            str(run_root),
            "--task-level",
            args.task_level,
            "--category",
            args.category,
            "--max-iter-times",
            str(args.max_iter_times),
            "--instance-json",
            str(instance_path),
        ]
        if args.instance_id:
            cmd.extend(["--instance-id", args.instance_id])

        print("[launch] in-container:", " ".join(cmd))
        returncode = launch_agent(
            container_id=container_id,
            cmd=cmd,
            cwd=run_root,
            env=env,
            log_path=log_path,
        )
        returncode = retry_launch_on_transient(
            returncode=returncode,
            log_path=log_path,
            args=args,
            label="airesearcher",
            relaunch=lambda: launch_agent(
                container_id=container_id,
                cmd=cmd,
                cwd=run_root,
                env=env,
                log_path=log_path,
                append=True,
            ),
        )
        if returncode != 0:
            print(f"[airesearcher] exited with code {returncode}. See {log_path}", file=sys.stderr)
            print_log_tail(log_path)
        return returncode
    finally:
        finalize_run_metadata(
            run_root,
            returncode=returncode,
            container_id=container_id,
            docker_workdir=docker_workdir,
            instance_path=instance_path,
            log_path=log_path if log_path.is_file() else None,
        )
        if destroy_sandbox:
            sandbox.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run AI-Researcher with ai_scientist sandbox on any task package"
    )
    parser.add_argument("--task-dir", default=str(DEFAULT_TASK_DIR))
    parser.add_argument("--task-level", default="task1", choices=["task1", "task2"])
    parser.add_argument(
        "--category",
        default="benchmark",
        help=(
            "InnoFlow category key used only as the metaprompt import suffix "
            "(default: benchmark). Integration always installs a task-derived "
            "metaprompt into sys.modules; do not rely on upstream ML categories."
        ),
    )
    parser.add_argument(
        "--instance-id",
        default="",
        help="Optional instance id override (default: derived from task dir name)",
    )
    parser.add_argument(
        "--instance-json",
        default="",
        help="Optional path to an existing AI-Researcher instance JSON "
        "(skips related_work synthesis when provided at prepare time)",
    )
    parser.add_argument(
        "--related-work",
        default="",
        help="Path to related_work.json / shortlist (default: <task-dir>/related_work.json)",
    )
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "7030")))
    parser.add_argument("--max-iter-times", type=int, default=int(os.getenv("MAX_ITER_TIMES", "0")))
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument(
        "--launch",
        action="store_true",
        help="Start TaskSandbox and launch InnoFlow inside the container",
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        help="Reuse an existing workspace/airesearcher_<ts> directory",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Destroy the sandbox when leaving prepare-only / non-launch mode",
    )
    parser.add_argument(
        "--no-keep-sandbox",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--native",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    add_transient_retry_arguments(parser)
    args = parser.parse_args()
    args.instance_json = args.instance_json or None
    args.related_work = args.related_work or None
    args.instance_id = args.instance_id or None

    if args.native or os.environ.get(BENCHMARK_AGENT_NATIVE_ENV) == "1":
        return run_native_flow(args)

    # Default: prepare + launch (matches prior always-launch behavior when no flags).
    if not args.prepare_only and not args.launch:
        args.launch = True

    return run_pipeline(Path(args.task_dir).resolve(), args)


if __name__ == "__main__":
    raise SystemExit(main())
