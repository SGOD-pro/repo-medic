import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from src.config import settings
from src.contracts import TaskRecipe
from src.engine.adapters import CommandResult, SandboxAdapter

logger = logging.getLogger("repomedic.contree_sandbox")


def _parse_test_summary(stdout: str) -> Dict[str, Any]:
    """Parse pytest collection counts, skips, xfails, and node identifiers from stdout."""
    collected_count: Optional[int] = None
    skipped_count = 0
    xfailed_count = 0
    passed_count = 0
    failed_count = 0
    error_count = 0
    node_ids: List[str] = []

    # 1. Look for collection count
    collect_match = re.search(r"collected\s+(\d+)\s+items?", stdout, re.IGNORECASE)
    if collect_match:
        collected_count = int(collect_match.group(1))

    # Look for status counts
    passed_match = re.search(r"(?:=+\s*)?(\d+)\s+passed", stdout, re.IGNORECASE)
    if passed_match:
        passed_count = int(passed_match.group(1))

    failed_match = re.search(r"(\d+)\s+failed", stdout, re.IGNORECASE)
    if failed_match:
        failed_count = int(failed_match.group(1))

    error_match = re.search(r"(\d+)\s+errors?", stdout, re.IGNORECASE)
    if error_match:
        error_count = int(error_match.group(1))

    # 2. Look for skipped count
    skip_match = re.search(r"(\d+)\s+skipped", stdout, re.IGNORECASE)
    if skip_match:
        skipped_count = int(skip_match.group(1))

    # 3. Look for xfailed count
    xfail_match = re.search(r"(\d+)\s+xfailed", stdout, re.IGNORECASE)
    if xfail_match:
        xfailed_count = int(xfail_match.group(1))

    # 4. Extract pytest node identifiers
    for line in stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith(("<", "!", "=", "WARNING")):
            for part in line.split():
                if "::" in part:
                    node_ids.append(part)
                    break

    if collected_count is None or collected_count == 0:
        total_counted = passed_count + failed_count + error_count + skipped_count + xfailed_count
        if total_counted > 0:
            collected_count = total_counted
        elif node_ids:
            collected_count = len(node_ids)
        else:
            collected_count = 0

    return {
        "collected_count": collected_count,
        "skipped_count": skipped_count,
        "xfailed_count": xfailed_count,
        "collected_node_ids": sorted(list(set(node_ids))),
    }


class ConTreeSandboxAdapter(SandboxAdapter):
    """
    Live sandbox adapter connecting to Nebius ConTree Sandbox SDK.
    Manages isolated container instances, immutable image snapshot checkpoints,
    ephemeral candidate execution branches, and clean resource teardown.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        project_id: Optional[str] = None,
        base_image: Optional[str] = None,
        client: Optional[Any] = None,
        current_image: Optional[Any] = None,
        working_dir: str = "/workspace",
        checkpoint_id: str = "",
        is_execution_handle: bool = False,
        timeout_seconds: int = 600,
        installed_version: str = "",
        import_origin: str = "",
    ):
        if api_key is not None:
            self.api_key = api_key.strip()
        else:
            self.api_key = (os.getenv("NEBIUS_API_KEY") or settings.nebius_api_key).strip()

        if project_id is not None:
            self.project_id = project_id.strip()
        else:
            self.project_id = (
                os.getenv("NEBIUS_PROJECT_ID")
                or settings.nebius_project_id
                or settings.token_factory_sandbox_project_id
            ).strip()

        self.base_image = (
            base_image or settings.nebius_sandbox_image or "python:3.12-bookworm"
        ).strip()
        self.working_dir = working_dir
        self.checkpoint_id = checkpoint_id
        self.is_execution_handle = is_execution_handle
        self.timeout_seconds = timeout_seconds

        self.current_image = current_image
        self.snapshots: List[str] = []
        self.execution_handles: List["ConTreeSandboxAdapter"] = []
        self.cleaned_up: bool = False
        self.executed_commands: List[List[str]] = []
        self.installed_version = installed_version
        self.import_origin = import_origin

        if client is not None:
            self.client = client
        elif is_execution_handle:
            self.client = None
        else:
            if not self.api_key or not self.project_id:
                raise ValueError(
                    "ConTreeSandboxAdapter requires NEBIUS_API_KEY and NEBIUS_PROJECT_ID credentials."
                )
            try:
                from contree_sdk import Contree  # type: ignore[import-untyped]
                from contree_sdk.auth import IAMAuth  # type: ignore[import-untyped]
                from contree_sdk.config import ContreeConfig  # type: ignore[import-untyped]

                auth = IAMAuth(token=self.api_key, project_id=self.project_id)
                config = ContreeConfig(auth=auth, operation_timeout=float(self.timeout_seconds))
                self.client = Contree(config=config)
            except ImportError as err:
                raise RuntimeError(
                    f"contree-sdk is not installed or importable: {err}"
                ) from err

    async def _ensure_image(self) -> Any:
        """Resolve base image if not yet initialized."""
        if self.current_image is not None:
            return self.current_image

        if self.client is None:
            raise RuntimeError("ConTree client is not initialized")

        try:
            self.current_image = await self.client.images.docker(self.base_image)
            return self.current_image
        except Exception as exc:
            raise RuntimeError(
                f"Failed to acquire base sandbox container image '{self.base_image}': {exc}"
            ) from exc

    async def prepare_repository(self, recipe: TaskRecipe) -> None:
        """
        Clones target repository at pinned commit SHA, verifies HEAD, and installs base packages.
        """
        await self._ensure_image()

        # 1. Clone repository
        clone_cmd = ["git", "clone", recipe.repository_url, self.working_dir]
        clone_res = await self.execute_command(clone_cmd, timeout_seconds=180)
        if clone_res.exit_code != 0:
            err = clone_res.stderr or clone_res.stdout or f"exit code {clone_res.exit_code}"
            raise RuntimeError(f"Failed to clone repository '{recipe.repository_url}': {err}")

        # 2. Checkout pinned commit
        checkout_cmd = ["git", "checkout", recipe.commit_sha]
        checkout_res = await self.execute_command(checkout_cmd, timeout_seconds=60)
        if checkout_res.exit_code != 0:
            err = checkout_res.stderr or checkout_res.stdout or f"exit code {checkout_res.exit_code}"
            raise RuntimeError(f"Failed to checkout commit '{recipe.commit_sha}': {err}")

        # 3. Verify HEAD commit matches recipe
        rev_cmd = ["git", "rev-parse", "HEAD"]
        rev_res = await self.execute_command(rev_cmd, timeout_seconds=30)
        observed_sha = rev_res.stdout.strip()
        expected_sha = recipe.commit_sha.strip()
        sha_matches = (
            observed_sha == expected_sha
            or observed_sha.startswith(expected_sha)
            or expected_sha.startswith(observed_sha)
        )
        if not sha_matches:
            raise RuntimeError(
                f"Working tree commit mismatch: expected '{recipe.commit_sha}', got '{observed_sha}'"
            )

        # 4. Install base dependencies
        dep_cmd = ["pip", "install", "-r", "requirements.txt"]
        dep_res = await self.execute_command(dep_cmd, timeout_seconds=180)
        if dep_res.exit_code != 0:
            fallback_cmd = ["pip", "install", "-e", "."]
            fallback_res = await self.execute_command(fallback_cmd, timeout_seconds=180)
            if fallback_res.exit_code != 0:
                logger.warning(
                    "Base dependency installation returned non-zero (requirements.txt: %s, fallback: %s)",
                    dep_res.stderr or dep_res.stdout,
                    fallback_res.stderr or fallback_res.stdout,
                )
        if recipe.task_id == "TASK-092":
            # Reproduce verified local environment: install pinned baseline, sqlite driver, and pytest harness
            env_setup_cmd = [
                "pip",
                "install",
                f"{recipe.dependency}=={recipe.from_version}",
                "aiosqlite",
                "pytest",
                "pytest-asyncio",
            ]
            await self.execute_command(env_setup_cmd, timeout_seconds=180)

    async def execute_command(
        self, command: List[str], timeout_seconds: int = 60
    ) -> CommandResult:
        """
        Executes command in ConTree container.
        Runs commands statefully inside sandbox or execution branch, with cleanup handling teardown.
        Parses test counts, installed package metadata, and node IDs from command output.
        """
        current_img = await self._ensure_image()
        self.executed_commands.append(list(command))

        effective_timeout = min(timeout_seconds, self.timeout_seconds)
        cmd_head = command[0] if command else ""
        cmd_args = command[1:] if len(command) > 1 else []

        try:
            run_kwargs = {
                "command": cmd_head,
                "args": cmd_args,
                "cwd": self.working_dir,
                "env": {"GIT_TERMINAL_PROMPT": "0"},
                "timeout": effective_timeout,
                "disposable": False,
            }
            new_img = await current_img.run(**run_kwargs)
            self.current_image = new_img
        except TimeoutError as exc:
            raise TimeoutError(
                f"Execution timed out after {effective_timeout} seconds"
            ) from exc
        except Exception as exc:
            raise RuntimeError(
                f"Remote ConTree sandbox command execution failed: {exc}"
            ) from exc

        # Parse outputs
        raw_exit = getattr(new_img, "exit_code", 0)
        exit_code = int(raw_exit) if raw_exit is not None else 0

        raw_stdout = getattr(new_img, "stdout", "")
        if isinstance(raw_stdout, bytes):
            stdout = raw_stdout.decode("utf-8", errors="replace")
        else:
            stdout = str(raw_stdout or "")

        raw_stderr = getattr(new_img, "stderr", "")
        if isinstance(raw_stderr, bytes):
            stderr = raw_stderr.decode("utf-8", errors="replace")
        else:
            stderr = str(raw_stderr or "")

        # Test summary parsing
        parsed = _parse_test_summary(stdout)
        collected_count = parsed["collected_count"]
        skipped_count = parsed["skipped_count"]
        xfailed_count = parsed["xfailed_count"]
        collected_node_ids = parsed["collected_node_ids"]

        # Installed version parsing for pip install operations
        installed_version = ""
        import_origin = ""
        is_pip_install = cmd_head == "pip" and "install" in cmd_args
        if is_pip_install and exit_code == 0:
            pkg_name = ""
            for arg in cmd_args:
                if "==" in arg:
                    pkg_name = arg.split("==")[0].strip()
                    break
            if pkg_name:
                mod_name = pkg_name.replace("-", "_")
                ver_script = (
                    "import sys\n"
                    f"pkg = '{pkg_name}'\n"
                    f"mod = '{mod_name}'\n"
                    "ver = ''\n"
                    "origin = 'site-packages'\n"
                    "try:\n"
                    "    m = __import__(mod)\n"
                    "    ver = str(getattr(m, '__version__', ''))\n"
                    "    mf = str(getattr(m, '__file__', ''))\n"
                    "    if 'site-packages' not in mf and mf:\n"
                    "        origin = mf\n"
                    "except Exception:\n"
                    "    try:\n"
                    "        import importlib.metadata\n"
                    "        ver = importlib.metadata.version(pkg)\n"
                    "    except Exception:\n"
                    "        pass\n"
                    "print(ver)\n"
                    "print(origin)\n"
                )
                ver_check_cmd = ["python3", "-c", ver_script]
                try:
                    ver_img = await self.current_image.run(
                        command=ver_check_cmd[0],
                        args=ver_check_cmd[1:],
                        cwd=self.working_dir,
                        timeout=30,
                        disposable=False,
                    )
                    v_raw = getattr(ver_img, "stdout", "")
                    v_lines = (
                        v_raw.decode("utf-8") if isinstance(v_raw, bytes) else str(v_raw or "")
                    ).strip().splitlines()
                    installed_version = v_lines[0].strip() if len(v_lines) > 0 else ""
                    import_origin = v_lines[1].strip() if len(v_lines) > 1 else "site-packages"
                    self.installed_version = installed_version
                    self.import_origin = import_origin
                except Exception:
                    installed_version = ""

        return CommandResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            collected_count=collected_count,
            skipped_count=skipped_count,
            xfailed_count=xfailed_count,
            installed_version=installed_version or self.installed_version,
            import_origin=import_origin or self.import_origin,
            collected_node_ids=collected_node_ids,
        )

    async def apply_patch(self, diff_content: str) -> CommandResult:
        """
        Uploads candidate patch to /tmp/candidate.patch and executes git apply in sandbox.
        """
        current_img = await self._ensure_image()
        patch_path = "/tmp/candidate.patch"
        clean_patch = diff_content if diff_content.endswith("\n") else (diff_content + "\n")
        patch_bytes = clean_patch.encode("utf-8")

        try:
            new_img = await current_img.run(
                command="git",
                args=["apply", "--recount", "--unidiff-zero", "--whitespace=nowarn", patch_path],
                cwd=self.working_dir,
                files={patch_path: patch_bytes},
                timeout=60,
                disposable=False,
            )
            self.current_image = new_img
        except TimeoutError as exc:
            raise TimeoutError("Patch application timed out after 60 seconds") from exc
        except Exception as exc:
            raise RuntimeError(f"Patch injection failed: {exc}") from exc

        raw_exit = getattr(new_img, "exit_code", 0)
        exit_code = int(raw_exit) if raw_exit is not None else 0

        raw_stdout = getattr(new_img, "stdout", "")
        stdout = raw_stdout.decode("utf-8") if isinstance(raw_stdout, bytes) else str(raw_stdout or "")

        raw_stderr = getattr(new_img, "stderr", "")
        stderr = raw_stderr.decode("utf-8") if isinstance(raw_stderr, bytes) else str(raw_stderr or "")

        return CommandResult(exit_code=exit_code, stdout=stdout, stderr=stderr)

    async def capture_checkpoint(self, tag: Optional[str] = None) -> str:
        """
        Captures sandbox image state as an immutable snapshot checkpoint UUID.
        """
        current_img = await self._ensure_image()
        raw_uuid = getattr(current_img, "uuid", None)
        checkpoint_id = str(raw_uuid) if raw_uuid else (tag or f"chk_{id(current_img)}")

        tag_as_fn = getattr(current_img, "tag_as", None)
        if tag and callable(tag_as_fn):
            try:
                tagged_img = await tag_as_fn(tag)
                if tagged_img is not None:
                    self.current_image = tagged_img
            except Exception as exc:
                logger.warning("Failed to tag snapshot checkpoint with '%s': %s", tag, exc)

        self.checkpoint_id = checkpoint_id
        self.snapshots.append(checkpoint_id)
        return checkpoint_id

    async def create_execution(self, checkpoint_id: str) -> "ConTreeSandboxAdapter":
        """
        Branches ephemeral execution container instance from immutable snapshot checkpoint.
        """
        if self.client is None:
            raise RuntimeError("Cannot create execution without ConTree client")

        try:
            branch_image = await self.client.images.use(checkpoint_id)
        except Exception as exc:
            raise RuntimeError(
                f"Failed to branch sandbox container from checkpoint '{checkpoint_id}': {exc}"
            ) from exc

        child = ConTreeSandboxAdapter(
            api_key=self.api_key,
            project_id=self.project_id,
            base_image=self.base_image,
            client=self.client,
            current_image=branch_image,
            working_dir=self.working_dir,
            checkpoint_id=checkpoint_id,
            is_execution_handle=True,
            timeout_seconds=self.timeout_seconds,
            installed_version=self.installed_version,
            import_origin=self.import_origin,
        )
        self.execution_handles.append(child)
        return child

    async def hash_files(
        self, paths_or_patterns: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Calculates SHA-256 hashes of repository files, explicitly excluding .git,
        __pycache__, and .pytest_cache directories to prevent cache tampering false positives.
        """
        await self._ensure_image()

        hash_script = """
import hashlib, json, os, sys
patterns = json.loads(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1] != 'null' else None
results = {}
exclude_dirs = {'.git', '__pycache__', '.pytest_cache', '.venv', 'node_modules', '.mypy_cache', 'dist', 'build'}
test_configs = {'conftest.py', 'pytest.ini', 'setup.cfg', 'tox.ini', 'pyproject.toml'}

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    rel_root = os.path.normpath(root)
    is_test_dir = (
        rel_root == 'tests' or rel_root.startswith('tests' + os.sep) or
        rel_root == 'test' or rel_root.startswith('test' + os.sep) or
        rel_root == 'testing' or rel_root.startswith('testing' + os.sep)
    )
    for f in sorted(files):
        if f.endswith('.pyc') or f.endswith('.pyo'):
            continue
        rel = os.path.normpath(os.path.join(root, f))
        if patterns:
            if not any(p in rel for p in patterns):
                continue
        else:
            if not (is_test_dir or (rel_root == '.' and f in test_configs)):
                continue
        try:
            with open(rel, 'rb') as fp:
                results[rel] = hashlib.sha256(fp.read()).hexdigest()
        except Exception:
            pass
print(json.dumps(results))
"""
        cmd = [
            "python3",
            "-c",
            hash_script,
            json.dumps(paths_or_patterns) if paths_or_patterns else "null",
        ]
        res = await self.execute_command(cmd, timeout_seconds=30)
        if res.exit_code == 0 and res.stdout.strip():
            raw_out = res.stdout.strip()
            start_idx = raw_out.rfind("{")
            end_idx = raw_out.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                json_str = raw_out[start_idx:end_idx + 1]
                try:
                    data = json.loads(json_str)
                    if isinstance(data, dict):
                        return data
                except Exception:
                    pass
        return {}

    async def cleanup(self) -> None:
        """
        Terminates remote sandbox containers, snapshots, and releases resources cleanly.
        """
        # 1. Clean up child execution handles
        for child in self.execution_handles:
            try:
                await child.cleanup()
            except Exception as exc:
                logger.warning("Error cleaning up child execution handle: %s", exc)

        # 2. Untag snapshot images if tagged
        untag_fn = getattr(self.current_image, "untag", None) if self.current_image else None
        if callable(untag_fn):
            try:
                await untag_fn()
            except Exception:
                pass

        self.cleaned_up = True
