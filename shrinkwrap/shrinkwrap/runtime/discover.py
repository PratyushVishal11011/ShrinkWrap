from __future__ import annotations

import json
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Optional

from shrinkwrap.runtime.python import PythonRuntime
from shrinkwrap.errors import PythonRuntimeError


SUPPORTED_MAJOR_MINOR = {"3.11", "3.12", "3.13"}


def discover_python_runtime(
    *,
    python_executable: Optional[Path] = None,
) -> PythonRuntime:
    exe = _resolve_python_executable(python_executable)

    info = _query_python_runtime(exe)

    major_minor = _extract_major_minor(info["version"])
    if major_minor not in SUPPORTED_MAJOR_MINOR:
        raise PythonRuntimeError(
            f"Unsupported Python version {info['version']} "
            f"(supported: {', '.join(sorted(SUPPORTED_MAJOR_MINOR))})"
        )

    return PythonRuntime(
        python_executable=exe,
        version=info["version"],
        stdlib_path=Path(info["stdlib"]),
        libpython_path=Path(info["libpython"]) if info["libpython"] else None,
    )


def _resolve_python_executable(explicit: Optional[Path]) -> Path:
    if explicit:
        exe = explicit
    else:
        found = shutil.which("python3")
        if not found:
            raise PythonRuntimeError("No python3 found in PATH")
        exe = Path(found)

    if not exe.exists():
        raise PythonRuntimeError(f"Python executable not found: {exe}")

    return exe.resolve()


def _query_python_runtime(exe: Path) -> dict:
    probe = r"""
import sys, sysconfig, json, pathlib

version = sys.version.split()[0]
stdlib = sysconfig.get_path("stdlib")

libpython = None
ldlibrary = sysconfig.get_config_var("LDLIBRARY")
libdir = sysconfig.get_config_var("LIBDIR")

if ldlibrary and libdir:
    candidate = pathlib.Path(libdir) / ldlibrary
    if candidate.exists() and candidate.suffix in (".so", ".dylib"):
        libpython = str(candidate)

print(json.dumps({
    "version": version,
    "stdlib": stdlib,
    "libpython": libpython,
}))
"""

    try:
        result = subprocess.run(
            [str(exe), "-c", probe],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise PythonRuntimeError(
            f"Failed to query Python runtime:\n{exc.stderr}"
        ) from exc

    return json.loads(result.stdout.strip())


def _extract_major_minor(version: str) -> str:
    parts = version.split(".")
    if len(parts) < 2:
        raise PythonRuntimeError(f"Invalid Python version: {version}")
    return f"{parts[0]}.{parts[1]}"
