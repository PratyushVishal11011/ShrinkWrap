from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from shrinkwrap.bundle.formats.directory import _validate_layout
from shrinkwrap.bundle.layout import BundleLayout
from shrinkwrap.errors import BuildError


@dataclass(frozen=True)
class OptimizeStats:
    files_removed: int = 0
    directories_removed: int = 0
    bytes_reclaimed: int = 0
    packages_removed: int = 0


def optimize_bundle(
    layout: BundleLayout,
    *,
    strip_bytecode: bool = True,
    strip_tests: bool = True,
    strip_metadata: bool = True,
    strip_type_hints: bool = True,
    strip_packaging_tools: bool = True,
    strip_dist_info: bool = False,
    remove_build_artifacts: bool = True,
    aggressive_stdlib_trim: bool = False,
    remove_packages: Iterable[str] | None = None,
    extra_globs: Iterable[str] | None = None,
) -> OptimizeStats:

    _validate_layout(layout)

    stats = OptimizeStats()

    targets: list[Path] = []

    if strip_bytecode:
        targets.extend(_find_all(layout, ["**/*.pyc", "**/*.pyo"]))
        targets.extend(_find_all(layout, ["**/__pycache__"], directories_only=True))

    if strip_tests:
        targets.extend(
            _find_all(
                layout,
                ["site-packages/**/tests", "site-packages/**/test"],
                directories_only=True,
            )
        )

    if strip_metadata:
        targets.extend(
            _find_all(
                layout,
                [
                    "site-packages/**/docs",
                    "site-packages/**/examples",
                    "site-packages/**/example",
                    "site-packages/**/benchmark*",
                    "site-packages/**/LICENSE*",
                    "site-packages/**/COPYING*",
                    "site-packages/**/NOTICE*",
                    "site-packages/**/README*",
                    "site-packages/**/*.md",
                    "site-packages/**/*.rst",
                ],
            )
        )

    if strip_type_hints:
        targets.extend(_find_all(layout, ["site-packages/**/*.pyi", "site-packages/**/py.typed"]))

    if strip_packaging_tools:
        targets.extend(
            _find_all(
                layout,
                [
                    "site-packages/pip",
                    "site-packages/setuptools",
                    "site-packages/wheel",
                    "site-packages/pip-*",
                    "site-packages/setuptools-*",
                    "site-packages/wheel-*",
                ],
            )
        )

    if strip_dist_info:
        targets.extend(_find_all(layout, ["site-packages/**/*.dist-info", "site-packages/**/*.egg-info"], directories_only=True))

    if remove_build_artifacts:
        targets.extend(
            _find_all(
                layout,
                [
                    "dist",
                    "build",
                    "*.egg-info",
                    "requirements*.txt",
                    ".DS_Store",
                ],
            )
        )

    if aggressive_stdlib_trim:
        stdlib_trim = [
            "ensurepip",
            "distutils",
            "lib2to3",
            "idlelib",
            "tkinter",
            "turtledemo",
            "venv",
            "test",
        ]
        targets.extend(
            _find_all(
                layout,
                [f"{name}" for name in stdlib_trim],
                base_override=[layout.stdlib_dir],
                directories_only=True,
            )
        )

    if remove_packages:
        pkg_targets: list[str] = []
        for pkg in remove_packages:
            pkg_targets.extend(
                [
                    f"site-packages/{pkg}",
                    f"site-packages/{pkg}-*",
                    f"site-packages/{pkg.replace('_', '-')}",
                    f"site-packages/{pkg.replace('_', '-')}-*",
                ]
            )
        targets.extend(_find_all(layout, pkg_targets))

    if extra_globs:
        targets.extend(_find_all(layout, list(extra_globs)))

    files_removed = 0
    directories_removed = 0
    bytes_reclaimed = 0
    packages_removed = 0

    for path in _dedupe_paths(targets):
        if not path.exists():
            continue

        try:
            if path.is_dir():
                bytes_reclaimed += _dir_size(path)
                _remove_dir(path)
                directories_removed += 1
                if _looks_like_package(path):
                    packages_removed += 1
            else:
                bytes_reclaimed += path.stat().st_size
                path.unlink()
                files_removed += 1
        except OSError as exc:
            raise BuildError(f"Failed to remove '{path}': {exc}") from exc

    return OptimizeStats(
        files_removed=files_removed,
        directories_removed=directories_removed,
        bytes_reclaimed=bytes_reclaimed,
        packages_removed=packages_removed,
    )


def _find_all(
    layout: BundleLayout,
    patterns: Iterable[str],
    *,
    directories_only: bool = False,
    base_override: Iterable[Path] | None = None,
) -> list[Path]:
    base_paths = list(base_override) if base_override else [
        layout.app_dir,
        layout.site_packages_dir,
        layout.stdlib_dir / "site-packages",
    ]

    matches: list[Path] = []
    for base in base_paths:
        for pattern in patterns:
            for candidate in base.glob(pattern):
                if directories_only and not candidate.is_dir():
                    continue
                matches.append(candidate)
    return matches


def _dedupe_paths(paths: Iterable[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in sorted(paths, key=lambda p: (len(p.as_posix()), p.as_posix())):
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _dir_size(path: Path) -> int:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file())


def _remove_dir(path: Path) -> None:
    for child in path.iterdir():
        if child.is_dir():
            _remove_dir(child)
        else:
            child.unlink()
    path.rmdir()


def _looks_like_package(path: Path) -> bool:
    name = path.name
    return name.endswith(".dist-info") or name.endswith(".egg-info") or (
        path.parent.name == "site-packages" and path.is_dir()
    )
