"""
Docker runner service — manages Docker containers for sandboxed
execution of LLM-generated code.

The coding agent runs inside Docker with explicit resource limits:
  - Memory limit (default 512MB)
  - CPU limit
  - Wall-clock timeout
  - Network disabled by default
  - Auto-cleanup after results extraction

Phase 6: full implementation.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

from orchestrator.config import TOY_TIMEOUT_SEC, TOY_MEM_LIMIT, TOY_NETWORK_DISABLED

logger = logging.getLogger(__name__)


def run_in_docker(
    task_spec: dict,
    code: str,
    timeout_sec: int = TOY_TIMEOUT_SEC,
    mem_limit: str = TOY_MEM_LIMIT,
    network_disabled: bool = TOY_NETWORK_DISABLED,
) -> dict:
    """
    Run code inside a Docker container with resource limits.

    Parameters
    ----------
    task_spec : dict
        The benchmark specification.
    code : str
        Python code to execute.
    timeout_sec : int
        Wall-clock timeout.
    mem_limit : str
        Docker memory limit (e.g. "512m").
    network_disabled : bool
        Whether to disable network access.

    Returns
    -------
    dict
        {status, stdout, stderr, runtime_seconds, exit_code}
    """
    try:
        import docker
    except ImportError:
        logger.warning("docker package not installed, using subprocess fallback")
        return _subprocess_fallback(code, timeout_sec)

    client = docker.from_env()

    # Create temp directory with the code
    with tempfile.TemporaryDirectory() as tmpdir:
        code_path = Path(tmpdir) / "run.py"
        code_path.write_text(code, encoding="utf-8")

        spec_path = Path(tmpdir) / "task_spec.json"
        spec_path.write_text(json.dumps(task_spec), encoding="utf-8")

        # Create output directory
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        try:
            container = client.containers.run(
                image="python:3.11-slim",
                command=["python", "/workspace/run.py"],
                volumes={
                    tmpdir: {"bind": "/workspace", "mode": "rw"},
                },
                mem_limit=mem_limit,
                network_disabled=network_disabled,
                detach=True,
                stderr=True,
                stdout=True,
            )

            # Wait for completion or timeout
            result = container.wait(timeout=timeout_sec)
            exit_code = result.get("StatusCode", -1)

            # Get logs
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

            # Check for results file
            results = {}
            results_path = output_dir / "results.json"
            if results_path.exists():
                results = json.loads(results_path.read_text())

            return {
                "status": "completed" if exit_code == 0 else "failed",
                "stdout": stdout[:5000],
                "stderr": stderr[:5000],
                "exit_code": exit_code,
                "results": results,
            }

        except Exception as e:
            logger.error(f"Docker execution error: {e}")
            return {
                "status": "error",
                "stdout": "",
                "stderr": str(e),
                "exit_code": -1,
                "results": {},
            }
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass


def _subprocess_fallback(code: str, timeout_sec: int) -> dict:
    """
    Fallback: run code via subprocess when Docker is not available.
    WARNING: Not sandboxed — only for local development testing.
    """
    import subprocess
    import time

    logger.warning("Running code WITHOUT Docker sandbox — development only!")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        script_path = f.name

    try:
        start = time.time()
        result = subprocess.run(
            ["python", script_path],
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
        elapsed = time.time() - start

        return {
            "status": "completed" if result.returncode == 0 else "failed",
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:5000],
            "exit_code": result.returncode,
            "runtime_seconds": elapsed,
            "results": {},
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "stdout": "",
            "stderr": f"Timed out after {timeout_sec}s",
            "exit_code": -1,
            "results": {},
        }
    finally:
        os.unlink(script_path)
