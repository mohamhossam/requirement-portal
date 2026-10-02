"""Architecture dependency validation tests.

These tests verify that the Clean Architecture layer contracts defined
in .importlinter are actually enforced against the real package
dependency graph of smb_requirement_agent.

The test invokes import-linter via subprocess exactly as the quality
gate command ``lint-imports`` does — it does NOT assert strings or
constants; it exercises the live import graph.
"""

import subprocess
import sys


def test_clean_architecture_contracts_pass() -> None:
    """All .importlinter contracts must hold.

    Contracts enforced:
    - Domain must not depend on Application, Infrastructure, or Interfaces.
    - Application must not depend on Infrastructure or Interfaces.
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from importlinter.cli import lint_imports; raise SystemExit(lint_imports())",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "One or more import-linter contracts failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
