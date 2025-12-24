import subprocess
from pathlib import Path
from typing import List, Optional

from shrinkwrap.errors import ShrinkwrapError


class SubprocessError(ShrinkwrapError):
    exit_code = 13

def run_command(
    command: List[str],
    *,
    cwd: Optional[Path] = None,
    env: Optional[dict] = None,
    check: bool = True,
    capture_output: bool = True,
    text: bool = True,
) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            env=env,
            check=False,  # handled manually
            capture_output=capture_output,
            text=text,
        )
    except FileNotFoundError as exc:
        raise SubprocessError(
            f"Command not found: {command[0]}"
        ) from exc
    except OSError as exc:
        raise SubprocessError(
            f"Failed to execute command: {' '.join(command)}"
        ) from exc

    if check and result.returncode != 0:
        raise SubprocessError(
            _format_error(command, result)
        )

    return result

def _format_error(
    command: List[str],
    result: subprocess.CompletedProcess,
) -> str:
    message = [
        f"Command failed: {' '.join(command)}",
        f"Exit code: {result.returncode}",
    ]

    if result.stdout:
        message.append(f"stdout:\n{result.stdout.strip()}")

    if result.stderr:
        message.append(f"stderr:\n{result.stderr.strip()}")

    return "\n".join(message)
