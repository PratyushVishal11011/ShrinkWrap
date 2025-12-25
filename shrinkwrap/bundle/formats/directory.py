from __future__ import annotations

import os
import stat
from pathlib import Path

from shrinkwrap.bundle.layout import BundleLayout
from shrinkwrap.errors import BuildError

def finalize_directory_bundle(
    layout: BundleLayout,
    *,
    entrypoint: str,
    output_name: str = "run",
) -> Path:

    _validate_layout(layout)

    if layout.is_windows:
        launcher_path = layout.root / f"{output_name}.bat"
        _write_windows_launcher(
            launcher_path=launcher_path,
            layout=layout,
            entrypoint=entrypoint,
        )
        return launcher_path

    launcher_path = layout.root / output_name
    _write_posix_launcher(
        launcher_path=launcher_path,
        layout=layout,
        entrypoint=entrypoint,
    )

    _make_executable(launcher_path)

    return launcher_path

def _validate_layout(layout: BundleLayout) -> None:

    required_paths = [
        layout.python_executable,
        layout.stdlib_dir,
        layout.app_dir,
        layout.site_packages_dir,
    ]

    for path in required_paths:
        if not path.exists():
            raise BuildError(
                f"Bundle layout incomplete, missing: {path}"
            )


def _write_posix_launcher(
    launcher_path: Path,
    *,
    layout: BundleLayout,
    entrypoint: str,
) -> None:

    stdlib_rel = layout.stdlib_dir.relative_to(layout.root).as_posix()
    lib_dynload_rel = (
        (layout.stdlib_dir / "lib-dynload").relative_to(layout.root).as_posix()
    )

    pythonpath = ":".join(
        [
            "$ROOT/app",
            "$ROOT/site-packages",
            f"$ROOT/{stdlib_rel}",
            f"$ROOT/{lib_dynload_rel}",
        ]
    )

    script = f"""#!/usr/bin/env bash
set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"

export PYTHONHOME="$ROOT/runtime"
export PYTHONPATH="{pythonpath}"
export PYTHONNOUSERSITE=1

exec "$ROOT/runtime/bin/python" -m uvicorn "{entrypoint}" --host 0.0.0.0 --port 8000
"""

    try:
        launcher_path.write_text(script)
    except OSError as exc:
        raise BuildError(
            f"Failed to write launcher script: {launcher_path}"
        ) from exc


def _write_windows_launcher(
    launcher_path: Path,
    *,
    layout: BundleLayout,
    entrypoint: str,
) -> None:

    stdlib_rel = layout.stdlib_dir.relative_to(layout.root)
    lib_dynload_rel = (layout.stdlib_dir / "lib-dynload").relative_to(layout.root)
    dlls_rel = layout.dlls_dir.relative_to(layout.root)

    def _rel(path: Path) -> str:
        return path.as_posix().replace("/", "\\")

    pythonpath = ";".join(
        [
            r"%ROOT%\app",
            r"%ROOT%\site-packages",
            f"%ROOT%\\{_rel(stdlib_rel)}",
            f"%ROOT%\\{_rel(lib_dynload_rel)}",
            f"%ROOT%\\{_rel(dlls_rel)}",
        ]
    )

    script = f"""@echo off
setlocal
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

set "PYTHONHOME=%ROOT%\runtime"
set "PYTHONPATH={pythonpath}"
set "PYTHONNOUSERSITE=1"
set "PATH=%ROOT%\runtime\DLLs;%ROOT%\runtime;%PATH%"

"%ROOT%\runtime\python.exe" -m uvicorn "{entrypoint}" --host 0.0.0.0 --port 8000 %*
"""

    try:
        launcher_path.write_text(script)
    except OSError as exc:
        raise BuildError(
            f"Failed to write launcher script: {launcher_path}"
        ) from exc


def _make_executable(path: Path) -> None:
    try:
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError as exc:
        raise BuildError(
            f"Failed to mark launcher executable: {path}"
        ) from exc
