import hashlib
import json
import shutil
from pathlib import Path
from typing import List, Literal, Optional

from shrinkwrap.utils.fs import ensure_dir, remove_dir
from shrinkwrap.utils.subprocess import run_command
from shrinkwrap.errors import BuildError


def install_dependencies(
    *,
    python_executable: Path,
    requirements: List[str],
    output_dir: Path,
    python_version: str,
    platform: Literal["posix", "windows"],
    cache_dir: Optional[Path] = None,
) -> Path:

    if not requirements:
        raise BuildError("No dependencies provided for installation")

    uv_executable = _resolve_uv()

    cache_root = cache_dir or Path.home() / ".cache" / "shrinkwrap" / "deps"
    key = _cache_key(requirements, python_version, platform)
    cached_path = cache_root / key

    if cached_path.exists():
        _copy_cached_dependencies(cached_path, output_dir)
        return output_dir

    ensure_dir(cache_root)
    staging = cache_root / f"{key}.tmp"
    remove_dir(staging)
    ensure_dir(staging)

    try:
        _install_to_target(uv_executable, python_executable, requirements, staging)
    except Exception:
        remove_dir(staging)
        raise

    remove_dir(cached_path)
    shutil.move(str(staging), cached_path)
    _copy_cached_dependencies(cached_path, output_dir)
    return output_dir


def _cache_key(requirements: List[str], python_version: str, platform: str) -> str:
    payload = json.dumps(
        {
            "python": python_version,
            "platform": platform,
            "requirements": sorted(requirements),
        },
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def _install_to_target(
    uv_executable: Path,
    python_executable: Path,
    requirements: List[str],
    target: Path,
) -> None:
    cmd = [
        str(uv_executable),
        "pip",
        "install",
        "--python",
        str(python_executable),
        "--target",
        str(target),
        "--no-compile",
    ] + requirements
    run_command(cmd)


def _copy_cached_dependencies(source: Path, destination: Path) -> None:
    remove_dir(destination)
    ensure_dir(destination.parent)
    shutil.copytree(source, destination, dirs_exist_ok=True)


def _resolve_uv() -> Path:
    executable = shutil.which("uv")
    if not executable:
        raise BuildError("uv executable not found in PATH")
    return Path(executable)
