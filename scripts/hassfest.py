"""Run Hassfest with one explicit exception for our intentional core override."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# This integration intentionally needs python-fints 4+, unlike HA's bundled one.
# Keep the full validator enabled; only this exact known conflict is tolerated.
EXPECTED_CONFLICT = (
    "* [ERROR] [REQUIREMENTS] Requirement fints>=4.2.4 is incompatible with "
    "fints==3.1.0, which Home Assistant depends on."
)


def main() -> int:
    """Preserve all other validation errors and unexpected process failures."""
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{root}:/github/workspace",
            "ghcr.io/home-assistant/hassfest",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    output = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    errors = [line.strip() for line in output.splitlines() if "[ERROR]" in line]
    expected_only = result.returncode == 1 and errors == [EXPECTED_CONFLICT]
    if expected_only:
        output = output.replace(
            EXPECTED_CONFLICT, "* [WARNING] Intentional override: fints>=4.2.4 (core pins 3.1.0)"
        )
    print(output, end="")
    if expected_only:
        print("::warning::FinTS 4+ intentionally overrides the core FinTS 3.1.0 dependency.")
        return 0
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
