from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Set, Tuple

from shrinkwrap.analyze.imports import build_import_graph, is_stdlib_module
from shrinkwrap.bundle.layout import BundleLayout
from shrinkwrap.config import BuildConfig
from shrinkwrap.errors import BuildError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PrunePlan:
    used_modules: Set[str]
    unused_packages: Set[str]
    unmapped_modules: Set[str]
    module_to_packages: Dict[str, Set[str]]
    package_to_modules: Dict[str, Set[str]]


def collect_used_modules(config: BuildConfig) -> Set[str]:
    graph = build_import_graph(config.entrypoint_module(), config.project_root)

    used: Set[str] = set()
    for module in graph.all_imports():
        top_level = module.split(".")[0]
        if not top_level:
            continue
        used.add(top_level)

    return {name for name in used if not is_stdlib_module(name)}


def plan_pruning(
    *,
    config: BuildConfig,
    layout: BundleLayout,
    allow_packages: Iterable[str] | None = None,
    deny_packages: Iterable[str] | None = None,
) -> PrunePlan:

    module_to_packages, package_to_modules, all_packages = _build_site_packages_index(
        layout.site_packages_dir
    )

    allow_normalized = {_normalize_name(name) for name in allow_packages or []}
    deny_normalized = {_normalize_name(name) for name in deny_packages or []}

    used_modules = collect_used_modules(config)

    unmapped = {
        module
        for module in used_modules
        if module not in module_to_packages and not _is_local_module(module, layout.app_dir)
    }
    if unmapped:
        logger.warning(
            "Skipping pruning; could not map modules: %s",
            ", ".join(sorted(unmapped)),
        )
        return PrunePlan(
            used_modules=used_modules,
            unused_packages=set(),
            unmapped_modules=unmapped,
            module_to_packages=module_to_packages,
            package_to_modules=package_to_modules,
        )

    packages_needed: Set[str] = set()
    for module in used_modules:
        packages_needed.update(module_to_packages.get(module, set()))

    unused_packages = {pkg for pkg in all_packages if pkg not in packages_needed}
    if allow_normalized:
        unused_packages = {
            pkg for pkg in unused_packages if _normalize_name(pkg) not in allow_normalized
        }
    if deny_normalized:
        unused_packages.update(
            pkg for pkg in all_packages if _normalize_name(pkg) in deny_normalized
        )

    return PrunePlan(
        used_modules=used_modules,
        unused_packages=unused_packages,
        unmapped_modules=unmapped,
        module_to_packages=module_to_packages,
        package_to_modules=package_to_modules,
    )


def _build_site_packages_index(
    site_packages_dir: Path,
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Set[str]]:

    if not site_packages_dir.exists():
        raise BuildError(
            f"Dependencies directory not found: {site_packages_dir}"
        )

    module_to_packages: Dict[str, Set[str]] = {}
    package_to_modules: Dict[str, Set[str]] = {}
    all_packages: Set[str] = set()

    for dist_info in site_packages_dir.glob("*.dist-info"):
        package_name = _dist_info_package_name(dist_info)
        all_packages.add(package_name)
        for module in _read_top_level(dist_info):
            _link_module_package(module, package_name, module_to_packages, package_to_modules)

    for item in site_packages_dir.iterdir():
        if item.name.endswith(".dist-info"):
            continue

        if item.name.endswith(".egg-info"):
            package_name = _strip_metadata_suffix(item.name, ".egg-info")
            all_packages.add(_strip_version(package_name))
            continue

        module_name = _module_name_from_path(item)
        if not module_name:
            continue

        if module_name in module_to_packages:
            continue

        guessed_package = _match_package(module_name, all_packages) or module_name
        all_packages.add(guessed_package)
        _link_module_package(module_name, guessed_package, module_to_packages, package_to_modules)

    return module_to_packages, package_to_modules, all_packages


def _read_top_level(dist_info: Path) -> Set[str]:
    top_level = dist_info / "top_level.txt"
    modules: Set[str] = set()

    if top_level.exists():
        try:
            for line in top_level.read_text().splitlines():
                name = line.strip()
                if name:
                    modules.add(name)
        except OSError as exc:
            logger.debug("Failed to read top_level.txt for %s: %s", dist_info, exc)

    return modules


def _dist_info_package_name(dist_info: Path) -> str:
    metadata = dist_info / "METADATA"
    if metadata.exists():
        try:
            for line in metadata.read_text().splitlines():
                if line.startswith("Name:"):
                    name = line.split(":", 1)[1].strip()
                    if name:
                        return name
        except OSError as exc:
            logger.debug("Failed to read METADATA for %s: %s", dist_info, exc)

    return _strip_version(_strip_metadata_suffix(dist_info.name, ".dist-info"))


def _strip_metadata_suffix(name: str, suffix: str) -> str:
    if name.endswith(suffix):
        return name[: -len(suffix)]
    return name


def _strip_version(name: str) -> str:
    parts = name.split("-")
    if len(parts) >= 2 and any(part[0].isdigit() for part in parts[-1:]):
        return "-".join(parts[:-1])
    return name


def _module_name_from_path(path: Path) -> str | None:
    if path.is_dir():
        if (path / "__init__.py").exists():
            return path.name
        return None

    if path.suffix == ".py":
        return path.stem

    return None


def _match_package(module_name: str, packages: Iterable[str]) -> str | None:
    target = _normalize_name(module_name)
    for package in packages:
        if _normalize_name(package) == target:
            return package
    return None


def _link_module_package(
    module: str,
    package: str,
    module_to_packages: Dict[str, Set[str]],
    package_to_modules: Dict[str, Set[str]],
) -> None:
    module_to_packages.setdefault(module, set()).add(package)
    package_to_modules.setdefault(package, set()).add(module)


def _normalize_name(name: str) -> str:
    return name.replace("_", "-").lower()


def _is_local_module(module: str, app_root: Path) -> bool:
    if not module:
        return False

    relative_parts = module.split(".")
    module_path = app_root.joinpath(*relative_parts)

    if module_path.with_suffix(".py").exists():
        return True

    if module_path.is_dir():
        return True

    return False