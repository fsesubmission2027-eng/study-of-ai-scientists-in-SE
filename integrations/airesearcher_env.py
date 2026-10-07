"""Path C: connect AI-Researcher agents to ai_scientist_benchmark TaskSandbox."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
AI_RESEARCHER_ROOT = BENCHMARK_ROOT.parent / "AI-Researcher"
ORCHESTRATOR_ROOT = BENCHMARK_ROOT / "orchestrator"
INTEGRATIONS_ROOT = BENCHMARK_ROOT / "integrations"
if str(ORCHESTRATOR_ROOT) not in sys.path:
    sys.path.insert(0, str(ORCHESTRATOR_ROOT))
if str(INTEGRATIONS_ROOT) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS_ROOT))

from agent_container import BENCHMARK_AGENT_NATIVE_ENV, BENCHMARK_RUN_ROOT_ENV, workdir_for_run  # noqa: E402
from path_alignment import load_task_env  # noqa: E402
from sandbox import TaskSandbox  # noqa: E402
from seed_staging import shell_copy_agent_seeds, stage_seeds_for_agent  # noqa: E402


class AiScientistDockerEnv:
    """Execute commands in the task sandbox (native in-container or legacy docker exec)."""

    def __init__(
        self,
        sandbox: TaskSandbox,
        local_workplace: str,
        workplace_name: str = "workspace",
        container_name: str | None = None,
        communication_port: int = 7020,
        *,
        native: bool = False,
    ):
        self.sandbox = sandbox
        self.local_workplace = local_workplace
        self.workplace_name = workplace_name
        self.container_name = container_name or sandbox.container_name
        self.communication_port = communication_port
        self.docker_workplace = workdir_for_run(Path(local_workplace))
        self.container_id = sandbox.container_id
        self.native = native or os.environ.get(BENCHMARK_AGENT_NATIVE_ENV) == "1"

    def init_container(self) -> None:
        if self.native:
            self._seed_workspace()
            return
        if self.container_id:
            return
        self.container_id = self.sandbox.start(
            agent_tool="airesearcher",
            run_root=Path(self.local_workplace),
        )
        self.container_name = self.sandbox.container_name
        self._seed_workspace()

    def _seed_workspace(self) -> None:
        seeds = self.sandbox.task_dir / "seeds"
        seeds_path = self.sandbox.seeds_path()
        req = f"{seeds_path}/requirements.txt"
        if Path(req).exists() or (seeds / "requirements.txt").exists():
            self.run_command(f"python3 -m pip install -r {req}")
        copy_cmd = shell_copy_agent_seeds(seeds, f"{self.local_workplace}/dataset_candidate")
        self.run_command(
            f"mkdir -p {self.local_workplace}/dataset_candidate "
            f"{self.local_workplace}/project {self.local_workplace}/results "
            f"{self.local_workplace}/paper {self.local_workplace}/downloads && "
            f"{copy_cmd}"
        )

    def stop_container(self) -> None:
        if self.native:
            return
        self.sandbox.destroy()
        self.container_id = None

    def run_command(self, command: str, stream_callback=None) -> dict[str, int | str]:
        if not self.container_id and not self.native:
            raise RuntimeError("Container is not running. Call init_container() first.")

        if self.native:
            proc = subprocess.run(
                ["bash", "-lc", command],
                cwd=self.local_workplace,
                capture_output=True,
                text=True,
                check=False,
            )
        else:
            cmd = [
                "docker",
                "exec",
                "-w",
                self.docker_workplace,
                self.container_id,
                "bash",
                "-lc",
                command,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)

        output = proc.stdout
        if proc.stderr:
            output = (output + "\n" + proc.stderr).strip()

        if stream_callback and output:
            for line in output.splitlines(keepends=True):
                stream_callback(line)

        return {"status": proc.returncode, "result": output}


def setup_dataset(
    category: str,
    local_workplace: str,
    *,
    task_dir: Path | None = None,
) -> None:
    """Ensure ``dataset_candidate/`` is populated from task seeds (preferred) or legacy AI-Researcher datasets."""
    dataset_candidate_path = os.path.join(local_workplace, "dataset_candidate")
    os.makedirs(dataset_candidate_path, exist_ok=True)
    if any(os.scandir(dataset_candidate_path)):
        return

    run_root = Path(local_workplace)
    resolved_task = task_dir
    if resolved_task is None:
        # Prefer parent of workspace/airesearcher_* ; fall back to parent of workplace/
        if run_root.parent.name == "workspace":
            resolved_task = run_root.parent.parent
        else:
            resolved_task = run_root.parent

    seeds = resolved_task / "seeds"
    if seeds.is_dir() and any(seeds.iterdir()):
        stage_seeds_for_agent(
            seeds,
            Path(dataset_candidate_path),
            task_env=load_task_env(resolved_task),
        )
        if any(os.scandir(dataset_candidate_path)):
            return

    source_path = AI_RESEARCHER_ROOT / "benchmark" / "process" / "dataset_candidate" / category
    if source_path.exists():
        shutil.copytree(source_path, dataset_candidate_path, dirs_exist_ok=True)
        return

    # Soft-fail: many benchmark tasks have no packaged dataset yet.
    print(
        f"[airesearcher] dataset_candidate empty and no legacy source at {source_path}; "
        "continuing without a pre-seeded dataset.",
        file=sys.stderr,
    )


def build_env(
    task_dir: Path,
    *,
    native: bool = False,
    run_root: Path | None = None,
) -> AiScientistDockerEnv:
    sandbox = TaskSandbox(task_dir, agent_tool="airesearcher")
    if run_root is None:
        raw = (os.environ.get(BENCHMARK_RUN_ROOT_ENV) or "").strip()
        if raw:
            run_root = Path(raw).resolve()
    if run_root is None:
        run_root = (task_dir / "workspace").resolve()
    else:
        run_root = run_root.resolve()
    os.makedirs(run_root, exist_ok=True)
    return AiScientistDockerEnv(
        sandbox=sandbox,
        local_workplace=str(run_root),
        workplace_name=run_root.name,
        native=native,
    )
