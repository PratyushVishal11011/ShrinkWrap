import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from shrinkwrap.runtime.python import PythonRuntime
from shrinkwrap.errors import PythonRuntimeError

SUPPORTED_VERSIONS = {"3.10", "3.11", "3.12"}

def discover_python_runtime(
    *,
    python_executable: Optional[Path] = None,
) -> PythonRuntime:
    exe = _resolve_python_executable(python_executable)

    info = _query_python_runtime(exe)
    major_minor = _extract_major_minor(info["version"])
    if major_minor not in SUPPORTED_VERSIONS:
        raise PythonRuntimeError(
            f"Unsupported Python version {info['version']} "
            f"(supported: {', '.join(sorted(SUPPORTED_VERSIONS))})"
        )

    return PythonRuntime(
        platform=info["platform"],
        python_executable=exe,
        version=info["version"],
        stdlib_path=Path(info["stdlib"]),
        libpython_path=Path(info["libpython"])
        if info.get("libpython")
        else None,
        python_zip=Path(info["python_zip"])
        if info.get("python_zip")
        else None,
        dlls_path=Path(info["dlls_dir"])
        if info.get("dlls_dir")
        else None,
    )


def _resolve_python_executable(explicit: Optional[Path]) -> Path:
    if explicit:
        exe = explicit
    else:
        exe: Optional[Path] = None
        for candidate in ("python3", "python"):
            found = shutil.which(candidate)
            if found:
                exe = Path(found)
                break

        if exe is None and os.name == "nt":
            py_launcher = shutil.which("py")
            if py_launcher:
                try:
                    result = subprocess.run(
                        [py_launcher, "-3", "-c", "import sys; print(sys.executable)"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    resolved = result.stdout.strip()
                    if resolved:
                        exe = Path(resolved)
                except subprocess.CalledProcessError:
                    exe = None

        if exe is None:
            raise PythonRuntimeError("No suitable python executable found in PATH")

    if not exe.exists():
        raise PythonRuntimeError(
            f"Python executable does not exist: {exe}"
        )

    return exe.resolve()


def _query_python_runtime(exe: Path) -> dict:
    probe_code = r"""
import json, os, pathlib, sys, sysconfig

platform = "windows" if os.name == "nt" else "posix"
version = sys.version.split()[0]
stdlib = sysconfig.get_path("stdlib")

major = sys.version_info[0]
minor = sys.version_info[1]
digits = f"{major}{minor}"

stdlib_path = pathlib.Path(stdlib) if stdlib else None

def dedupe(items):
    seen = set()
    out = []
    for item in items:
        if not item:
            continue
        path = pathlib.Path(item)
        key = path.resolve()
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out

lib_names = []
ldlibrary = sysconfig.get_config_var("LDLIBRARY")
if ldlibrary:
    lib_names.append(ldlibrary)

if platform == "windows":
    lib_names.extend([
        f"python{digits}.dll",
        f"libpython{major}.{minor}.dll",
    ])
else:
    lib_names.extend([
        f"libpython{major}.{minor}.so",
        f"libpython{major}.{minor}m.so",
        f"libpython{major}.{minor}.dylib",
    ])

lib_dirs = []
for key in ("LIBDIR", "BINDIR", "LIBPL", "LIBDEST"):
    value = sysconfig.get_config_var(key)
    if value:
        lib_dirs.append(value)

lib_dirs.extend([sys.prefix, sys.base_prefix, pathlib.Path(sys.executable).parent])

if stdlib_path:
    lib_dirs.append(stdlib_path.parent)
    lib_dirs.append(stdlib_path.parent / "DLLs")

libpython = None
for directory in dedupe(lib_dirs):
    for name in lib_names:
        if not name:
            continue
        candidate = directory / name
        suffix = candidate.suffix.lower()
        if not candidate.exists() or not candidate.is_file():
            continue
        if suffix == ".a":
            continue
        if platform == "windows" and suffix != ".dll":
            continue
        if platform == "posix" and suffix not in (".so", ".dylib"):
            continue
        libpython = str(candidate)
        break
    if libpython:
        break

python_zip = None
zip_name = f"python{digits}.zip"
zip_dirs = [
    stdlib_path,
    stdlib_path.parent if stdlib_path else None,
    stdlib_path.parent.parent if stdlib_path else None,
    pathlib.Path(sys.prefix),
    pathlib.Path(sys.base_prefix),
    pathlib.Path(sys.prefix) / "lib",
    pathlib.Path(sys.executable).parent,
]

for directory in dedupe(zip_dirs):
    candidate = directory / zip_name
    if candidate.exists() and candidate.is_file():
        python_zip = str(candidate)
        break

dlls_dir = None
if platform == "windows":
    dll_dirs = [
        pathlib.Path(sys.prefix) / "DLLs",
        pathlib.Path(sys.base_prefix) / "DLLs",
        pathlib.Path(sys.executable).parent / "DLLs",
    ]
    if stdlib_path:
        dll_dirs.append(stdlib_path.parent / "DLLs")

    for directory in dedupe(dll_dirs):
        if directory.exists() and directory.is_dir():
            dlls_dir = str(directory)
            break

print(json.dumps({
    "version": version,
    "stdlib": stdlib,
    "platform": platform,
    "libpython": libpython,
    "python_zip": python_zip,
    "dlls_dir": dlls_dir,
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