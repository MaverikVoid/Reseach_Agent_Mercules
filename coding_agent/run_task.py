"""
run_task.py — Entry point for Docker-sandboxed benchmark execution.

Reads TASK_SPEC from environment variable (JSON), generates and runs
the benchmark code, writes results to /output/results.json.
"""

import json
import os
import sys
import time
import traceback


def main():
    # Read task spec from environment
    task_spec_raw = os.environ.get("TASK_SPEC", "")
    if not task_spec_raw:
        print("ERROR: No TASK_SPEC environment variable found")
        sys.exit(1)

    try:
        task_spec = json.loads(task_spec_raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in TASK_SPEC: {e}")
        sys.exit(1)

    print(f"=== Benchmark Runner ===")
    print(f"Task: {json.dumps(task_spec, indent=2)[:500]}")

    # If there's direct code to execute
    code = task_spec.get("code", "")
    if not code:
        print("ERROR: No code in task spec")
        results = {"status": "error", "error": "No code provided"}
    else:
        results = execute_code(code, task_spec)

    # Write results
    output_path = "/output/results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print(f"\nResults written to {output_path}")
    print(f"Status: {results.get('status', 'unknown')}")


def execute_code(code: str, task_spec: dict) -> dict:
    """Execute the benchmark code and capture results."""
    # Write code to temp file
    code_path = "/tmp/benchmark.py"
    with open(code_path, "w") as f:
        f.write(code)

    start_time = time.time()

    try:
        # Execute in a subprocess for isolation
        import subprocess
        result = subprocess.run(
            [sys.executable, code_path],
            capture_output=True,
            text=True,
            timeout=task_spec.get("timeout_sec", 300),
            cwd="/tmp",
        )

        elapsed = time.time() - start_time

        return {
            "status": "completed" if result.returncode == 0 else "failed",
            "stdout": result.stdout[:10000],
            "stderr": result.stderr[:10000],
            "exit_code": result.returncode,
            "runtime_seconds": elapsed,
        }

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return {
            "status": "timeout",
            "runtime_seconds": elapsed,
            "error": f"Timed out after {task_spec.get('timeout_sec', 300)}s",
        }
    except Exception as e:
        elapsed = time.time() - start_time
        return {
            "status": "error",
            "runtime_seconds": elapsed,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


if __name__ == "__main__":
    main()
