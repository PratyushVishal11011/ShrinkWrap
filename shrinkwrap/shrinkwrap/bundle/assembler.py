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

        layout = BundleLayout(output_dir)

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
    shutil.copy2(runtime.python_executable, layout.python_executable)

    shutil.copytree(
        runtime.stdlib_path,
        layout.stdlib_dir,
        dirs_exist_ok=True,
    )

    lib_dynload = runtime.stdlib_path / "lib-dynload"
    if lib_dynload.exists():
        shutil.copytree(
            lib_dynload,
            layout.stdlib_dir / "lib-dynload",
            dirs_exist_ok=True,
        )


def _assemble_application(
    app_sources: Iterable[Path],
    layout: BundleLayout,
) -> None:

    for source in app_sources:
        if not source.exists():
            raise BuildError(
                f"Application source not found: {source}"
            )

        target = layout.app_dir / source.name

        if source.is_dir():
            shutil.copytree(
                source,
                target,
                dirs_exist_ok=True,
            )
        else:
            shutil.copy2(source, target)


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
