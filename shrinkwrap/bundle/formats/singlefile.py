from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from shrinkwrap.bundle.formats.directory import _validate_layout
from shrinkwrap.bundle.layout import BundleLayout
from shrinkwrap.errors import BundleFormatError, BuildError
from shrinkwrap.utils.fs import ensure_dir


def finalize_singlefile_bundle(
    layout: BundleLayout,
    *,
    output_file: Path | str,
    compression: Literal["gztar", "zip"] = "gztar",
) -> Path:
    """Package an assembled bundle directory into a single archive."""

    _validate_layout(layout)

    if compression not in {"gztar", "zip"}:
        raise BundleFormatError(
            f"Unsupported compression format: {compression}"
        )

    ext_map = {"gztar": ".tar.gz", "zip": ".zip"}
    output_path = _normalize_output_path(Path(output_file), ext_map[compression])

    try:
        ensure_dir(output_path.parent)
        archive_path = shutil.make_archive(
            base_name=str(output_path)[: -len(ext_map[compression])],
            format=compression,
            root_dir=layout.root,
        )
    except (OSError, shutil.Error) as exc:
        raise BuildError(
            f"Failed to create single-file archive: {output_path}"
        ) from exc

    return Path(archive_path)


def _normalize_output_path(output_path: Path, expected_ext: str) -> Path:
    if not str(output_path).endswith(expected_ext):
        return output_path.with_suffix("").with_suffix(expected_ext)
    return output_path
