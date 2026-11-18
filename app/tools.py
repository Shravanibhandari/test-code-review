import os
import subprocess
import sys
import tempfile

from langchain_core.tools import tool


def _run(args: list[str], cwd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", *args],
        capture_output=True, text=True, timeout=20, cwd=cwd,
        env={"PATH": os.environ.get("PATH", "")},  # don't leak secrets to the subprocess
    )


@tool
def run_linter_tool(code_string: str) -> str:
    """Writes python code to a temporary file and runs flake8 and black --check on it."""
    with tempfile.TemporaryDirectory() as tmp:  # isolated, auto-deleted
        path = os.path.join(tmp, "candidate.py")
        with open(path, "w") as f:
            f.write(code_string)
        try:
            flake = _run(["flake8", "--max-line-length=100", path], tmp)
            black = _run(["black", "--check", "--quiet", "-l", "100", path], tmp)
        except subprocess.TimeoutExpired:
            return "LINT_ERROR: linter timed out"
        parts = []
        if (flake.stdout + flake.stderr).strip():
            parts.append((flake.stdout + flake.stderr).strip())
        if black.returncode == 1:
            parts.append("black: would reformat candidate.py (formatting does not match black style)")
        elif black.returncode != 0 and "E999" not in "".join(parts):
            parts.append("black: " + black.stderr.strip())
        return "\n".join(parts).replace(path, "candidate.py") or "OK"
