"""
Compute dispatch service — submits full-scale benchmarks to remote GPU.

Primary: Kaggle Kernels API (free GPU quota)
Fallback: RunPod serverless API (paid on-demand)
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from orchestrator.config import (
    KAGGLE_USERNAME,
    KAGGLE_KEY,
    KAGGLE_POLL_INTERVAL_SEC,
    RUNPOD_API_KEY,
    RUNPOD_GPU_TYPE,
)

logger = logging.getLogger(__name__)


def dispatch_kaggle(
    kernel_code: str,
    kernel_title: str = "research-benchmark",
    dataset_sources: list[str] | None = None,
) -> dict:
    """
    Push a kernel to Kaggle and start execution.

    Returns {status, kernel_slug} or {status, error}.
    """
    if not KAGGLE_USERNAME or not KAGGLE_KEY:
        return {"status": "error", "error": "Kaggle credentials not configured"}

    # Set Kaggle env vars
    os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
    os.environ["KAGGLE_KEY"] = KAGGLE_KEY

    with tempfile.TemporaryDirectory() as tmpdir:
        # Write kernel code
        script_path = Path(tmpdir) / "script.py"
        script_path.write_text(kernel_code, encoding="utf-8")

        # Write kernel metadata
        slug = f"{KAGGLE_USERNAME}/{kernel_title}"
        metadata = {
            "id": slug,
            "title": kernel_title,
            "code_file": "script.py",
            "language": "python",
            "kernel_type": "script",
            "is_private": True,
            "enable_gpu": True,
            "enable_internet": True,
            "dataset_sources": dataset_sources or [],
            "competition_sources": [],
            "kernel_sources": [],
        }

        meta_path = Path(tmpdir) / "kernel-metadata.json"
        meta_path.write_text(json.dumps(metadata), encoding="utf-8")

        # Push kernel
        try:
            result = subprocess.run(
                ["kaggle", "kernels", "push", "-p", tmpdir],
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return {
                    "status": "error",
                    "error": f"Kaggle push failed: {result.stderr}",
                }

            return {
                "status": "submitted",
                "kernel_slug": slug,
            }

        except FileNotFoundError:
            return {
                "status": "error",
                "error": "Kaggle CLI not found. Install with: pip install kaggle",
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Kaggle push timed out"}


def poll_kaggle(kernel_slug: str, max_polls: int = 60) -> dict:
    """
    Poll Kaggle kernel status until completion.

    Returns {status, output} or {status, error}.
    """
    os.environ["KAGGLE_USERNAME"] = KAGGLE_USERNAME
    os.environ["KAGGLE_KEY"] = KAGGLE_KEY

    for i in range(max_polls):
        try:
            result = subprocess.run(
                ["kaggle", "kernels", "status", kernel_slug],
                capture_output=True,
                text=True,
                timeout=30,
            )

            output = result.stdout.strip()
            logger.info(f"Kaggle poll {i+1}/{max_polls}: {output}")

            if "complete" in output.lower():
                return {"status": "completed", "output": output}
            elif "error" in output.lower() or "cancelAcknowledged" in output:
                return {"status": "failed", "error": output}

            time.sleep(KAGGLE_POLL_INTERVAL_SEC)

        except Exception as e:
            logger.error(f"Kaggle poll error: {e}")
            time.sleep(KAGGLE_POLL_INTERVAL_SEC)

    return {"status": "timeout", "error": f"Kernel did not complete in {max_polls} polls"}


def dispatch_runpod(code: str, gpu_type: str = RUNPOD_GPU_TYPE) -> dict:
    """
    Fallback: submit job via RunPod serverless API.
    """
    if not RUNPOD_API_KEY:
        return {"status": "error", "error": "RunPod API key not configured"}

    try:
        import runpod
        runpod.api_key = RUNPOD_API_KEY

        # This is a simplified version — real implementation would
        # create an endpoint or use an existing one
        return {
            "status": "error",
            "error": "RunPod dispatch not yet fully implemented. "
                     "Configure a RunPod serverless endpoint first.",
        }

    except ImportError:
        return {"status": "error", "error": "runpod package not installed"}


def dispatch_full_benchmark(
    code: str,
    kernel_title: str = "research-benchmark",
) -> dict:
    """
    Try Kaggle first, fall back to RunPod if Kaggle fails.

    Returns the final result dict.
    """
    # Try Kaggle
    logger.info("Attempting Kaggle dispatch...")
    kaggle_result = dispatch_kaggle(code, kernel_title)

    if kaggle_result["status"] == "submitted":
        logger.info(f"Kaggle kernel submitted: {kaggle_result['kernel_slug']}")
        # Poll for completion
        poll_result = poll_kaggle(kaggle_result["kernel_slug"])
        if poll_result["status"] == "completed":
            return {
                "status": "completed",
                "compute_platform": "kaggle",
                "details": poll_result,
            }
        logger.warning(f"Kaggle failed: {poll_result}")

    # Fallback to RunPod
    logger.info("Kaggle failed, trying RunPod fallback...")
    runpod_result = dispatch_runpod(code)
    return {
        "status": runpod_result.get("status", "error"),
        "compute_platform": "runpod",
        "details": runpod_result,
    }
