from __future__ import annotations

from pathlib import Path
from typing import Iterable, Literal

from shrinkwrap.bundle.formats.directory import _validate_layout
from shrinkwrap.bundle.layout import BundleLayout
from shrinkwrap.errors import BundleFormatError, BuildError
from shrinkwrap.utils.fs import ensure_dir
from shrinkwrap.utils.subprocess import run_command


def finalize_squashfs_bundle(
    layout: BundleLayout,
    *,
    output_file: Path | str,
    mksquashfs: str = "mksquashfs",
    compression: Literal["xz", "gzip", "zstd"] = "xz",
    block_size: int = 1_048_576,
    extra_args: Iterable[str] | None = None,
) -> Path:
    """Create a SquashFS image from the assembled bundle."""

    _validate_layout(layout)

    if block_size <= 0:
        raise BundleFormatError("block_size must be positive")

    output_path = Path(output_file)
    ensure_dir(output_path.parent)

    cmd = [
        mksquashfs,
        str(layout.root),
        str(output_path),
        "-noappend",
        "-b",
        str(block_size),
        "-comp",
        compression,
    ]

    if extra_args:
        cmd.extend(list(extra_args))

    try:
        run_command(cmd, check=True, capture_output=True)
    except Exception as exc:
        raise BuildError(
            "Failed to create SquashFS image. Ensure mksquashfs is installed."
        ) from exc

    return output_path
