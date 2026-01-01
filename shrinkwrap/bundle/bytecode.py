from __future__ import annotations

import json
import os
import py_compile
import configparser
import textwrap
from email.parser import Parser
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile
from concurrent.futures import ProcessPoolExecutor
from itertools import repeat

_POOL_THRESHOLD = 8

from shrinkwrap.bundle.formats.directory import _validate_layout
from shrinkwrap.bundle.layout import BundleLayout
from shrinkwrap.errors import BuildError
from shrinkwrap.utils.fs import ensure_dir, remove_dir


def finalize_bytecode_bundle(
    layout: BundleLayout,
    *,
    build_pyz: bool = True,
    freeze_metadata: bool = True,
    strip_sources: bool = True,
    block_packaging: bool = True,
    optimize_level: int = 2,
) -> Path | None:

    _validate_layout(layout)

    app_sources = _list_sources(layout.app_dir)
    site_sources = _list_sources(layout.site_packages_dir)
    total_sources = len(app_sources) + len(site_sources)
    executor = ProcessPoolExecutor(max_workers=_worker_count()) if total_sources > _POOL_THRESHOLD else None

    try:
        _precompile_tree(layout.app_dir, optimize_level, executor=executor, sources=app_sources)
        _precompile_tree(layout.site_packages_dir, optimize_level, executor=executor, sources=site_sources)
    finally:
        if executor:
            executor.shutdown()

    _remove_pycache(layout.app_dir)
    _remove_pycache(layout.site_packages_dir)

    if strip_sources:
        _remove_sources(layout.app_dir)
        _remove_sources(layout.site_packages_dir)

    metadata = None
    if freeze_metadata:
        metadata = _collect_metadata(layout.site_packages_dir)
        _write_metadata(layout.metadata_dir, metadata)

    _write_sitecustomize(
        layout.metadata_dir,
        metadata_filename="importlib_metadata.json" if freeze_metadata else None,
        block_packaging=block_packaging,
    )

    if not build_pyz:
        return None

    return _write_pyz(layout)


def _precompile_tree(root: Path, optimize_level: int, *, executor: ProcessPoolExecutor | None = None, sources: list[Path] | None = None) -> None:
    if sources is None:
        sources = _list_sources(root)
    if not sources:
        return

    if executor is None and len(sources) <= _POOL_THRESHOLD:
        for source in sources:
            _compile_source(source, root, optimize_level)
        return

    if executor is None:
        with ProcessPoolExecutor(max_workers=_worker_count()) as pool:
            _drain_compile(pool, sources, root, optimize_level)
    else:
        _drain_compile(executor, sources, root, optimize_level)


def _drain_compile(executor: ProcessPoolExecutor, sources: list[Path], root: Path, optimize_level: int) -> None:
    iterator = executor.map(
        _compile_source,
        sources,
        repeat(root),
        repeat(optimize_level),
        chunksize=_chunksize(len(sources)),
    )
    for source in sources:
        try:
            next(iterator)
        except py_compile.PyCompileError as exc:
            raise BuildError(f"Failed to compile {source}: {exc.msg}") from exc
        except Exception as exc:
            raise BuildError(f"Failed to compile {source}: {exc}") from exc


def _compile_source(source: Path, root: Path, optimize_level: int) -> None:
    target = source.with_suffix(".pyc")
    rel = source.relative_to(root)
    py_compile.compile(
        str(source),
        cfile=str(target),
        optimize=optimize_level,
        dfile=str(rel),
    )


def _list_sources(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return list(root.rglob("*.py"))


def _worker_count() -> int:
    return min(32, (os.cpu_count() or 1))


def _chunksize(count: int) -> int:
    return 1 if count < 32 else 8


def _remove_pycache(root: Path) -> None:
    if not root.exists():
        return
    for cache_dir in root.rglob("__pycache__"):
        remove_dir(cache_dir)


def _remove_sources(root: Path) -> None:
    if not root.exists():
        return
    for source in root.rglob("*.py"):
        try:
            source.unlink()
        except OSError as exc:
            raise BuildError(f"Failed to remove source file {source}: {exc}") from exc


def _collect_metadata(site_packages: Path) -> dict:
    records: dict[str, dict] = {}

    if not site_packages.exists():
        return records

    for dist_info in site_packages.glob("*.dist-info"):
        metadata_file = dist_info / "METADATA"
        parser = Parser()
        try:
            headers = parser.parsestr(metadata_file.read_text()) if metadata_file.exists() else None
        except (OSError, UnicodeDecodeError):
            headers = None

        name = headers.get("Name") if headers else None
        version = headers.get("Version") if headers else None
        if not name or not version:
            continue

        entry_points = _parse_entry_points(dist_info / "entry_points.txt")
        packages = _parse_top_level(dist_info / "top_level.txt")
        requires = headers.get_all("Requires-Dist") if headers else None

        records[name.lower()] = {
            "name": name,
            "version": version,
            "entry_points": entry_points,
            "packages": packages,
            "requires": requires or [],
        }

    return records


def _parse_entry_points(path: Path) -> list[dict]:
    if not path.exists():
        return []

    parser = configparser.ConfigParser()
    try:
        parser.read(path)
    except configparser.Error:
        return []

    entries: list[dict] = []
    for group in parser.sections():
        for name, value in parser.items(group):
            entries.append({"group": group, "name": name, "value": value})
    return entries


def _parse_top_level(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        return [line.strip() for line in path.read_text().splitlines() if line.strip()]
    except OSError:
        return []


def _write_metadata(output_dir: Path, metadata: dict) -> None:
    ensure_dir(output_dir)
    target = output_dir / "importlib_metadata.json"
    try:
        target.write_text(json.dumps(metadata, indent=2, sort_keys=True))
    except OSError as exc:
        raise BuildError(f"Failed to write metadata to {target}: {exc}") from exc


def _write_sitecustomize(
    output_dir: Path,
    *,
    metadata_filename: str | None,
    block_packaging: bool,
) -> None:
    ensure_dir(output_dir)
    target = output_dir / "sitecustomize.py"

    metadata_loader = ""
    if metadata_filename:
        metadata_loader = f"_METADATA_PATH = Path(__file__).with_name(\"{metadata_filename}\")\n"
        metadata_loader += (
            "try:\n"
            "    _FROZEN_METADATA = json.loads(_METADATA_PATH.read_text())\n"
            "except Exception:\n"
            "    _FROZEN_METADATA = None\n\n"
        )
    else:
        metadata_loader = "_FROZEN_METADATA = None\n\n"

    blocked = (
        "_BLOCKED = {\"pip\", \"ensurepip\"}\n"
        "class _Blocked(types.ModuleType):\n"
        "    def __getattr__(self, name):\n"
        "        raise ImportError(f\"{{self.__name__}} is disabled in this runtime\")\n"
        "for _name in _BLOCKED:\n"
        "    sys.modules.setdefault(_name, _Blocked(_name))\n\n"
        if block_packaging
        else ""
    )

    sitecustomize = (
        textwrap.dedent(
            """
            import json
            import os
            import sys
            import types
            from pathlib import Path
            import importlib.metadata as _meta
            from importlib.metadata import EntryPoint, EntryPoints, PackageNotFoundError

            os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
            os.environ.setdefault("PYTHONNOUSERSITE", "1")
            os.environ.setdefault("PYTHONZIPIMPORT_USE_ZIPFILE", "1")
            """
        )
        + blocked
        + metadata_loader
        + textwrap.dedent(
            """
            if _FROZEN_METADATA:
                def _record_for(name: str) -> dict:
                    key = name.lower()
                    record = _FROZEN_METADATA.get(key)
                    if record is None:
                        raise PackageNotFoundError(name)
                    return record

                class _FrozenDistribution(_meta.Distribution):
                    def __init__(self, record: dict):
                        self._record = record

                    @property
                    def name(self) -> str:
                        return self._record["name"]

                    @property
                    def version(self) -> str:
                        return self._record["version"]

                    @property
                    def entry_points(self) -> EntryPoints:
                        eps = [EntryPoint(ep["name"], ep["value"], ep["group"]) for ep in self._record.get("entry_points", [])]
                        return EntryPoints(eps)

                    @property
                    def files(self):
                        return None

                    @property
                    def requires(self):
                        return self._record.get("requires") or None

                    @property
                    def metadata(self):
                        from email.message import Message
                        msg = Message()
                        msg["Name"] = self.name
                        msg["Version"] = self.version
                        return msg

                    def read_text(self, filename):
                        return None

                    def locate_file(self, path):
                        return Path(path)

                def distribution(name: str):
                    try:
                        return _FrozenDistribution(_record_for(name))
                    except PackageNotFoundError:
                        return _meta.distribution(name)

                def version(name: str):
                    try:
                        return _record_for(name)["version"]
                    except PackageNotFoundError:
                        return _meta.version(name)

                def entry_points(**params):
                    group = params.get("group")
                    name = params.get("name")
                    eps = []
                    for record in _FROZEN_METADATA.values():
                        for ep in record.get("entry_points", []):
                            if group and ep["group"] != group:
                                continue
                            if name and ep["name"] != name:
                                continue
                            eps.append(EntryPoint(ep["name"], ep["value"], ep["group"]))
                    if not eps:
                        return _meta.entry_points(**params)
                    return EntryPoints(eps)

                def packages_distributions():
                    mapping: dict[str, list[str]] = {}
                    for record in _FROZEN_METADATA.values():
                        for pkg in record.get("packages", []):
                            mapping.setdefault(pkg, []).append(record["name"])
                    return mapping

                _meta.distribution = distribution
                _meta.version = version
                _meta.entry_points = entry_points
                _meta.packages_distributions = packages_distributions
            """
        )
    )

    try:
        target.write_text(sitecustomize)
    except OSError as exc:
        raise BuildError(f"Failed to write sitecustomize.py: {exc}") from exc


def _write_pyz(layout: BundleLayout) -> Path:
    bundle_path = layout.root / "bundle.pyz"
    ensure_dir(bundle_path.parent)

    def should_skip(path: Path) -> bool:
        return path.suffix in {".so", ".pyd", ".dylib"}

    try:
        with ZipFile(bundle_path, "w", ZIP_DEFLATED) as zf:
            for base in (layout.app_dir, layout.site_packages_dir):
                if not base.exists():
                    continue
                for file in base.rglob("*"):
                    if file.is_dir() or should_skip(file):
                        continue
                    arcname = file.relative_to(layout.root).as_posix()
                    zf.write(file, arcname)
    except OSError as exc:
        raise BuildError(f"Failed to create bundle.pyz: {exc}") from exc

    return bundle_path
