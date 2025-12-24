import os
import subprocess
from typing import Dict, List, Optional

from shrinkwrap.errors import ShrinkwrapError


class LaunchError(ShrinkwrapError):
    exit_code = 30


def build_uvicorn_command(
    python_executable: str,
    entrypoint: str,
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
) -> List[str]:
    command = [
        python_executable,
        "-m",
        "uvicorn",
        entrypoint,
        "--host",
        host,
        "--port",
        str(port),
    ]

    if reload:
        command.append("--reload")

    return command


def launch_application(
    *,
    python_executable: str,
    entrypoint: str,
    env: Dict[str, str],
    cwd: Optional[str] = None,
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
) -> None:
    command = build_uvicorn_command(
        python_executable=python_executable,
        entrypoint=entrypoint,
        host=host,
        port=port,
        reload=reload,
    )

    try:
        process = subprocess.Popen(
            command,
            env=env,
            cwd=cwd,
        )
        process.wait()

        if process.returncode != 0:
            raise LaunchError(
                f"Application exited with code {process.returncode}"
            )

    except FileNotFoundError as exc:
        raise LaunchError(
            f"Python executable not found: {python_executable}"
        ) from exc

    except OSError as exc:
        raise LaunchError(
            "Failed to launch application"
        ) from exc
