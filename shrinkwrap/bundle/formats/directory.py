from __future__ import annotations

import stat
import textwrap
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

    script = textwrap.dedent(
        """
        #!/usr/bin/env bash
        set -e

        ROOT="$(cd "$(dirname "$0")" && pwd)"

        PYTHONPATH_ITEMS=()
        if [ -f "$ROOT/bundle.pyz" ]; then
            PYTHONPATH_ITEMS+=("$ROOT/bundle.pyz")
        fi
        PYTHONPATH_ITEMS+=("$ROOT/meta" "$ROOT/app" "$ROOT/site-packages" "$ROOT/{stdlib_rel}" "$ROOT/{lib_dynload_rel}")
        PYTHONPATH=$(IFS=:; echo "${{PYTHONPATH_ITEMS[*]}}")

        export PYTHONHOME="$ROOT/runtime"
        export PYTHONPATH
        export PYTHONNOUSERSITE=1
        export PYTHONDONTWRITEBYTECODE=1
        export PYTHONZIPIMPORT_USE_ZIPFILE=1

        exec "$ROOT/runtime/bin/python" -m uvicorn "{entrypoint}" --host 0.0.0.0 --port 8000
        """
    ).format(
        stdlib_rel=stdlib_rel,
        lib_dynload_rel=lib_dynload_rel,
        entrypoint=entrypoint,
    )

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

    script = textwrap.dedent(
        """
        @echo off
        setlocal
        set "ROOT=%~dp0"
        set "ROOT=%ROOT:~0,-1%"

        set "PYTHONPATH=%ROOT%\meta;%ROOT%\app;%ROOT%\site-packages;%ROOT%\\{stdlib_rel};%ROOT%\\{lib_dynload_rel};%ROOT%\\{dlls_rel}"
        if exist "%ROOT%\bundle.pyz" set "PYTHONPATH=%ROOT%\bundle.pyz;%PYTHONPATH%"

        set "PYTHONHOME=%ROOT%\runtime"
        set "PYTHONNOUSERSITE=1"
        set "PYTHONDONTWRITEBYTECODE=1"
        set "PYTHONZIPIMPORT_USE_ZIPFILE=1"
        set "PATH=%ROOT%\runtime\DLLs;%ROOT%\runtime;%PATH%"

        "%ROOT%\runtime\python.exe" -m uvicorn "{entrypoint}" --host 0.0.0.0 --port 8000 %*
        """
    ).format(
        stdlib_rel=_rel(stdlib_rel),
        lib_dynload_rel=_rel(lib_dynload_rel),
        dlls_rel=_rel(dlls_rel),
        entrypoint=entrypoint,
    )

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
