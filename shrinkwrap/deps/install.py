from pathlib import Path
from typing import List

from shrinkwrap.utils.fs import ensure_dir
from shrinkwrap.utils.subprocess import run_command
from shrinkwrap.errors import BuildError


def install_dependencies(
    *,
    python_executable: Path,
    requirements: List[str],
    output_dir: Path,
) -> Path:

    ensure_dir(output_dir)

    if not requirements:
        raise BuildError("No dependencies provided for installation")

    cmd = [
        str(python_executable),
        "-m",
        "pip",
        "install",
        "--no-compile",
        "-t",
        str(output_dir),
    ] + requirements

    run_command(cmd)

    return output_dir
