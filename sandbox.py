"""
sandbox.py — VibeOps Python Execution Sandbox
=============================================
Pillar 4: Advanced Tool Use (Sandbox Execution)

Safely executes user-provided Python code in an isolated process.
Captures stdout, stderr, tracebacks, and enforces a strict timeout.
"""

import sys
import time
import traceback
import subprocess
import tempfile
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from config import config


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    error: Optional[str]
    traceback: Optional[str]
    execution_time_sec: float
    timed_out: bool

    def __repr__(self):
        return (
            f"SandboxResult(time={self.execution_time_sec:.2f}s, "
            f"timeout={self.timed_out}, "
            f"stdout='{self.stdout.strip()}', "
            f"error='{self.error}')"
        )


class LocalPythonSandbox:
    """
    Isolated execution environment for Python code.
    Enforces a strict timeout and captures all standard outputs and errors.
    Uses subprocess (not multiprocessing) for reliable Windows operation.
    """
    def __init__(self):
        self.timeout = config().sandbox_timeout

    def execute(self, code: str) -> SandboxResult:
        """
        Executes Python code in a subprocess.

        Writes the code to a temp .py file, runs it via `python` subprocess,
        captures stdout/stderr. This avoids multiprocessing Queue deadlocks
        on Windows (spawn-mode issues).

        Args:
            code: Raw Python code string to execute.

        Returns:
            SandboxResult containing stdout, stderr, errors, and execution metrics.
        """
        project_root = Path(__file__).parent

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        start_time = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, tmp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                cwd=project_root,
            )
            execution_time = time.perf_counter() - start_time
            return SandboxResult(
                stdout=proc.stdout,
                stderr=proc.stderr,
                error=None if proc.returncode == 0 else f"Exit code {proc.returncode}",
                traceback=proc.stderr if proc.returncode != 0 else None,
                execution_time_sec=execution_time,
                timed_out=False,
            )

        except subprocess.TimeoutExpired:
            execution_time = time.perf_counter() - start_time
            return SandboxResult(
                stdout="",
                stderr="",
                error="TimeoutError: Execution exceeded the 10-second limit.",
                traceback=None,
                execution_time_sec=execution_time,
                timed_out=True,
            )

        except Exception as e:
            execution_time = time.perf_counter() - start_time
            tb = traceback.format_exc()
            return SandboxResult(
                stdout="",
                stderr="",
                error=str(e),
                traceback=tb,
                execution_time_sec=execution_time,
                timed_out=False,
            )

        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def execute_python_code(code: str) -> str:
    """
    Executes Python code in a safe sandbox and returns the stdout, stderr, and tracebacks.
    Use this tool to run code against data or perform any data analysis.

    Args:
        code: Raw Python code string to execute.

    Returns:
        A string containing execution metrics, stdout, stderr, and any tracebacks/errors.
    """
    sandbox = LocalPythonSandbox()
    result = sandbox.execute(code)

    return (
        f"Execution Time: {result.execution_time_sec:.2f}s\n"
        f"Timed Out: {result.timed_out}\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}\n"
        f"ERROR:\n{result.error or 'None'}\n"
        f"TRACEBACK:\n{result.traceback or 'None'}\n"
    )


# Smoke test
if __name__ == "__main__":
    sandbox = LocalPythonSandbox()
    test_code = "print(sum([1, 2, 3]))"
    print(f"Testing sandbox with code: '{test_code}'")
    result = sandbox.execute(test_code)
    print(f"Result: {result}")
