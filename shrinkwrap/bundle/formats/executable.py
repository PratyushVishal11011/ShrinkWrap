from __future__ import annotations

import shutil
import stat
import tempfile
import textwrap
from pathlib import Path

from shrinkwrap.bundle.formats.directory import (
    _make_executable,
    _validate_layout,
    _write_posix_launcher,
)
from shrinkwrap.bundle.layout import BundleLayout
from shrinkwrap.errors import BuildError
from shrinkwrap.utils.fs import ensure_dir


def finalize_executable_bundle(
    layout: BundleLayout,
    *,
    entrypoint: str,
    output_file: Path | str,
) -> Path:

    _validate_layout(layout)

    if layout.is_windows:
        raise BuildError(
            "Executable format currently supports only POSIX targets; use directory or singlefile on Windows."
        )

    output_path = Path(output_file)
    ensure_dir(output_path.parent)

    with tempfile.TemporaryDirectory() as tmp_dir:
        _ensure_posix_launcher(layout, entrypoint)
        archive_path = _make_archive(layout, output_path, Path(tmp_dir))
        launcher_script = _build_launcher_script()

        try:
            with open(output_path, "wb") as f:
                f.write(launcher_script.encode("utf-8"))
                with open(archive_path, "rb") as tar:
                    shutil.copyfileobj(tar, f)

            st = output_path.stat()
            output_path.chmod(st.st_mode | stat.S_IEXEC)

        except OSError as exc:
            raise BuildError(
                f"Failed to create executable: {output_path}"
            ) from exc

    return output_path


def _make_archive(layout: BundleLayout, output_path: Path, tmp_dir: Path) -> str:
    base_name = tmp_dir / "bundle"

    try:
        return shutil.make_archive(
            base_name=str(base_name),
            format="gztar",
            root_dir=layout.root,
            base_dir=".",  
        )
    except (OSError, shutil.Error) as exc:
        raise BuildError(
            f"Failed to create archive for executable: {output_path}"
        ) from exc


def _ensure_posix_launcher(layout: BundleLayout, entrypoint: str) -> None:
    launcher_path = layout.root / "run"

    if launcher_path.exists():
        return

    _write_posix_launcher(
        launcher_path=launcher_path,
        layout=layout,
        entrypoint=entrypoint,
    )
    _make_executable(launcher_path)


def _build_launcher_script() -> str:
    return (
        textwrap.dedent(
            """
            #!/bin/sh
            set -euo pipefail

            cleanup() {
                [ -n "${TMPDIR:-}" ] && [ -d "$TMPDIR" ] && rm -rf "$TMPDIR"
            }

            TMPDIR=$(mktemp -d /tmp/shrinkwrap.XXXXXX)
            trap cleanup EXIT INT TERM

            ARCHIVE_START=$(awk '/^__ARCHIVE_BELOW__/ {print NR + 1; exit 0; }' "$0")

            tail -n +"$ARCHIVE_START" "$0" | tar xz -C "$TMPDIR"

            "$TMPDIR/run" "$@"
            EXIT_CODE=$?

            exit $EXIT_CODE

            __ARCHIVE_BELOW__
            """
        ).strip()
        + "\n"
    )
