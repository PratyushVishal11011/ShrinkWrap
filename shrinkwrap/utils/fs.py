import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from shrinkwrap.errors import ShrinkwrapError


class FilesystemError(ShrinkwrapError):
    exit_code = 12

def ensure_dir(path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise FilesystemError(
            f"Failed to create directory: {path}"
        ) from exc


def remove_dir(path: Path) -> None:
    try:
        if path.exists():
            shutil.rmtree(path)
    except OSError as exc:
        raise FilesystemError(
            f"Failed to remove directory: {path}"
        ) from exc

@contextmanager
def temp_dir(prefix: str = "shrinkwrap-") -> Iterator[Path]:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    try:
        yield path
    finally:
        remove_dir(path)

def atomic_write(path: Path, data: bytes) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    try:
        with tmp_path.open("wb") as f:
            f.write(data)
        os.replace(tmp_path, path)
    except OSError as exc:
        raise FilesystemError(
            f"Failed to write file atomically: {path}"
        ) from exc
