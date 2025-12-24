import os
from pathlib import Path
from typing import Dict, Optional

from shrinkwrap.runtime.python import PythonRuntime
from shrinkwrap.errors import PythonRuntimeError


def build_runtime_env(
    runtime: PythonRuntime,
    *,
    app_root: Optional[Path] = None,
    extra_env: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    env: Dict[str, str] = {}
    _inherit_safe_env(env)

    env["PYTHONHOME"] = str(runtime.stdlib_path.parent)
    env["PYTHONPATH"] = _build_pythonpath(runtime, app_root)

    # Prevent user site-packages leakage
    env["PYTHONNOUSERSITE"] = "1"

    if runtime.libpython_path:
        lib_dir = runtime.libpython_path.parent
        _prepend_env_path(env, "LD_LIBRARY_PATH", lib_dir)

    if extra_env:
        for key, value in extra_env.items():
            env[key] = value

    return env

def _inherit_safe_env(env: Dict[str, str]) -> None:
    for key in (
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
    ):
        value = os.environ.get(key)
        if value is not None:
            env[key] = value


def _build_pythonpath(
    runtime: PythonRuntime,
    app_root: Optional[Path],
) -> str:
    paths = []

    if app_root:
        if not app_root.exists():
            raise PythonRuntimeError(
                f"Application root does not exist: {app_root}"
            )
        paths.append(str(app_root))

    paths.append(str(runtime.stdlib_path))

    return os.pathsep.join(paths)


def _prepend_env_path(
    env: Dict[str, str],
    key: str,
    value: Path,
) -> None:
    existing = env.get(key)
    if existing:
        env[key] = f"{value}{os.pathsep}{existing}"
    else:
        env[key] = str(value)
