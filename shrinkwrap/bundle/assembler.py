import shutil
from pathlib import Path
from typing import Iterable

from shrinkwrap.bundle.layout import BundleLayout
from shrinkwrap.config import BuildConfig
from shrinkwrap.runtime.python import PythonRuntime
from shrinkwrap.errors import BuildError
from shrinkwrap.utils.fs import ensure_dir, remove_dir

def assemble_bundle(
    *,
    config: BuildConfig,
    runtime: PythonRuntime,
    app_sources: Iterable[Path],
    dependencies_dir: Path,
    output_dir: Path,
) -> BundleLayout:

    try:
        remove_dir(output_dir)
        ensure_dir(output_dir)

        if runtime.is_windows:
            stdlib_relative = Path("Lib")
        else:
            stdlib_relative = Path("lib") / f"python{runtime.major_minor}"

        layout = BundleLayout(
            output_dir,
            stdlib_relative=stdlib_relative,
            platform=runtime.platform,
        )

        for directory in layout.all_dirs():
            ensure_dir(directory)

        _assemble_runtime(runtime, layout)
        _assemble_application(app_sources, layout)
        _assemble_dependencies(dependencies_dir, layout)

        return layout

    except Exception as exc:
        raise BuildError(
            f"Failed to assemble bundle: {exc}"
        ) from exc

def _assemble_runtime(
    runtime: PythonRuntime,
    layout: BundleLayout,
) -> None:

    ensure_dir(layout.python_executable.parent)
    shutil.copy2(
        runtime.python_executable,
        layout.python_executable,
    )

    if runtime.is_windows:
        exe_dir = runtime.python_executable.parent
        for dll in exe_dir.glob("vcruntime*.dll"):
            shutil.copy2(dll, layout.runtime_dir / dll.name)

    ensure_dir(layout.stdlib_dir.parent)
    shutil.copytree(
        runtime.stdlib_path,
        layout.stdlib_dir,
        dirs_exist_ok=True,
    )

    lib_dynload_src = runtime.stdlib_path / "lib-dynload"
    lib_dynload_dst = layout.stdlib_dir / "lib-dynload"

    if lib_dynload_src.exists():
        shutil.copytree(
            lib_dynload_src,
            lib_dynload_dst,
            dirs_exist_ok=True,
        )

    if runtime.dlls_path:
        ensure_dir(layout.dlls_dir.parent)
        shutil.copytree(
            runtime.dlls_path,
            layout.dlls_dir,
            dirs_exist_ok=True,
        )

    if runtime.python_zip:
        ensure_dir(layout.python_zip_dir)
        shutil.copy2(
            runtime.python_zip,
            layout.python_zip_dir / runtime.python_zip.name,
        )

    if runtime.libpython_path:
        ensure_dir(layout.libpython_dir)
        shutil.copy2(
            runtime.libpython_path,
            layout.libpython_dir / runtime.libpython_path.name,
        )

def _assemble_application(
    app_sources: Iterable[Path],
    layout: BundleLayout,
) -> None:

    layout_root = layout.root.resolve()

    def _ignore_layout_artifacts(dirpath: str, names: list[str]) -> list[str]:
        dir_path = Path(dirpath).resolve()
        ignored: list[str] = []
        for name in names:
            candidate = (dir_path / name).resolve()
            if candidate == layout_root or layout_root in candidate.parents:
                ignored.append(name)
        return ignored

    for source in app_sources:
        if not source.exists():
            raise BuildError(
                f"Application source not found: {source}"
            )

        if source.is_dir():
            ignore = None
            try:
                layout_root.relative_to(source.resolve())
                ignore = _ignore_layout_artifacts
            except ValueError:
                ignore = None

            shutil.copytree(
                source,
                layout.app_dir,
                dirs_exist_ok=True,
                ignore=ignore,
            )
        else:
            shutil.copy2(
                source,
                layout.app_dir / source.name,
            )


def _assemble_dependencies(
    dependencies_dir: Path,
    layout: BundleLayout,
) -> None:
    if not dependencies_dir.exists():
        raise BuildError(
            f"Dependencies directory not found: {dependencies_dir}"
        )

    shutil.copytree(
        dependencies_dir,
        layout.site_packages_dir,
        dirs_exist_ok=True,
    )
