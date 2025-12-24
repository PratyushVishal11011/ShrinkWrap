import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from shrinkwrap.runtime.python import PythonRuntime
from shrinkwrap.errors import PythonRuntimeError

SUPPORTED_MAJOR_MINOR = {"3.11"}

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
            f"(supported: {', '.join(SUPPORTED_MAJOR_MINOR)})"
        )

    return PythonRuntime(
        python_executable=exe,
        version=info["version"],
        stdlib_path=Path(info["stdlib"]),
        libpython_path=Path(info["libpython"])
        if info.get("libpython")
        else None,
        python_zip=Path(info["python_zip"])
        if info.get("python_zip")
        else None,
    )

def _resolve_python_executable(
    explicit: Optional[Path],
) -> Path:
    if explicit:
        exe = explicit
    else:
        found = shutil.which("python3")
        if not found:
            raise PythonRuntimeError(
                "No python3 executable found in PATH"
            )
        exe = Path(found)

    if not exe.exists():
        raise PythonRuntimeError(
            f"Python executable does not exist: {exe}"
        )

    return exe.resolve()


def _query_python_runtime(exe: Path) -> dict:

    probe_code = r"""
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

python_zip = None
if stdlib:
    stdlib_path = pathlib.Path(stdlib)
    zip_name = f"python{sys.version_info[0]}{sys.version_info[1]}.zip"
    candidate_dirs = [
        stdlib_path,
        stdlib_path.parent,
        stdlib_path.parent.parent,
        pathlib.Path(sys.prefix),
        pathlib.Path(sys.prefix) / "lib",
    ]

    for directory in candidate_dirs:
        candidate = directory / zip_name
        if candidate.exists():
            python_zip = str(candidate)
            break

print(json.dumps({
    "version": version,
    "stdlib": stdlib,
    "libpython": libpython,
    "python_zip": python_zip,
}))
"""

    try:
        result = subprocess.run(
            [str(exe), "-c", probe_code],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        raise PythonRuntimeError(
            f"Failed to query Python runtime: {exc.stderr}"
        ) from exc
    except OSError as exc:
        raise PythonRuntimeError(
            "Failed to execute Python interpreter"
        ) from exc

    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError as exc:
        raise PythonRuntimeError(
            "Invalid response while probing Python runtime"
        ) from exc


def _extract_major_minor(version: str) -> str:
    parts = version.split(".")
    if len(parts) < 2:
        raise PythonRuntimeError(
            f"Invalid Python version string: {version}"
        )
    return f"{parts[0]}.{parts[1]}"