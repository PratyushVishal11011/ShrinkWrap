import sys
from pathlib import Path
from typing import Literal

import typer

from shrinkwrap.analyze.entrypoint import analyze_entrypoint
from shrinkwrap.errors import ShrinkwrapError
from shrinkwrap.logger import setup_logger

from shrinkwrap.config import BuildConfig
from shrinkwrap.analyze.requirements import discover_requirements
from shrinkwrap.runtime.discover import discover_python_runtime
from shrinkwrap.runtime.env import build_runtime_env
from shrinkwrap.bundle.assembler import assemble_bundle
from shrinkwrap.bundle.bytecode import finalize_bytecode_bundle
from shrinkwrap.bundle.formats.directory import finalize_directory_bundle
from shrinkwrap.bundle.formats.singlefile import finalize_singlefile_bundle
from shrinkwrap.bundle.formats.squashfs import finalize_squashfs_bundle
from shrinkwrap.bundle.optimizer import optimize_bundle
from shrinkwrap.analyze.prune import plan_pruning
from shrinkwrap.deps.install import install_dependencies
from shrinkwrap.utils.fs import temp_dir


app = typer.Typer(
    name="shrinkwrap",
    help="Shrinkwrap: bundle FastAPI apps into minimal executables",
    add_completion=False,
)

@app.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
):

    setup_logger(verbose=verbose)

@app.command()
def analyze(
    entry: str = typer.Option(
        ...,
        "--entry",
        "-e",
        help="ASGI entrypoint (example: app.main:app)",
    ),
):

    try:
        typer.echo(f"Analyzing entrypoint: {entry}")
        analyze_entrypoint(entry)
        typer.echo("Entrypoint is a valid FastAPI application")

    except ShrinkwrapError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        sys.exit(1)

    except Exception:
        typer.secho(
            "Internal error occurred. Run with --verbose for details.",
            fg=typer.colors.RED,
            err=True,
        )
        raise

@app.command()
def build(
    entry: str = typer.Option(..., "--entry", "-e"),
    output: str = typer.Option("dist/app", "--output", "-o"),
    bundle_format: Literal["directory", "singlefile", "squashfs"] = typer.Option(
        "directory",
        "--format",
        "-f",
        case_sensitive=False,
        help="Bundle output format",
    ),
    optimize: bool = typer.Option(
        True,
        "--optimize/--no-optimize",
        help="Strip bytecode, tests, and other non-essential files",
    ),
    prune_unused: bool = typer.Option(
        True,
        "--prune-unused/--no-prune-unused",
        help="Remove dependencies that are not imported by the application",
    ),
    keep_package: list[str] = typer.Option(
        [],
        "--keep-package",
        "-k",
        help="Package(s) to keep even if unused (can be passed multiple times)",
    ),
    drop_package: list[str] = typer.Option(
        [],
        "--drop-package",
        "-d",
        help="Package(s) to force remove (can be passed multiple times)",
    ),
    zip_imports: bool = typer.Option(
        True,
        "--zip-imports/--no-zip-imports",
        help="Package app + deps into bundle.pyz and prefer zipimport",
    ),
    strip_sources: bool = typer.Option(
        True,
        "--strip-sources/--keep-sources",
        help="Drop .py after byte-compiling to .pyc",
    ),
    freeze_metadata: bool = typer.Option(
        True,
        "--freeze-metadata/--no-freeze-metadata",
        help="Freeze importlib.metadata to avoid filesystem scans",
    ),
    block_packaging: bool = typer.Option(
        True,
        "--block-packaging/--allow-packaging",
        help="Disable pip/ensurepip inside the bundled runtime",
    ),
):

    try:
        typer.echo("Building Shrinkwrap bundle")

        config = BuildConfig(
            entrypoint=entry,
            output_format=bundle_format,
            optimize=optimize,
            prune_unused=prune_unused,
            zip_imports=zip_imports,
            strip_sources=strip_sources,
            freeze_metadata=freeze_metadata,
            block_packaging=block_packaging,
        )

        typer.echo("Discovering Python runtime")
        runtime = discover_python_runtime()

        typer.echo("Discovering dependencies")
        requirements = discover_requirements(config.project_root)

        with temp_dir() as deps_dir:
            typer.echo("Preparing dependencies")
            site_packages = install_dependencies(
                python_executable=runtime.python_executable,
                requirements=requirements,
                output_dir=deps_dir / "site-packages",
                python_version=runtime.major_minor,
                platform=runtime.platform,
            )

            typer.echo("Assembling bundle")
            layout = assemble_bundle(
                config=config,
                runtime=runtime,
                app_sources=[config.project_root],
                dependencies_dir=site_packages,
                output_dir=Path(output)
                if bundle_format == "directory"
                else deps_dir / "bundle",
            )

            unused_packages: set[str] = set()

            if config.prune_unused:
                typer.echo("Analyzing imports for pruning")
                try:
                    prune_plan = plan_pruning(
                        config=config,
                        layout=layout,
                        allow_packages=set(keep_package),
                        deny_packages=set(drop_package),
                    )
                except ShrinkwrapError as exc:
                    typer.secho(
                        f"Skipping pruning due to error: {exc}",
                        fg=typer.colors.YELLOW,
                        err=True,
                    )
                else:
                    if prune_plan.unmapped_modules:
                        typer.secho(
                            "Skipping pruning; could not map modules: "
                            + ", ".join(sorted(prune_plan.unmapped_modules)),
                            fg=typer.colors.YELLOW,
                        )
                    else:
                        unused_packages = set(prune_plan.unused_packages)
                        if unused_packages:
                            typer.echo(
                                " - removing unused packages: "
                                + ", ".join(sorted(unused_packages))
                            )
                        else:
                            typer.echo(" - no unused packages detected")

            should_optimize = config.optimize or bool(unused_packages)

            if should_optimize:
                typer.echo("Optimizing bundle")
                optimize_kwargs = {}
                if not config.optimize:
                    optimize_kwargs = dict(
                        strip_bytecode=False,
                        strip_tests=False,
                        strip_metadata=False,
                        strip_type_hints=False,
                        strip_packaging_tools=False,
                        strip_dist_info=False,
                        remove_build_artifacts=False,
                        aggressive_stdlib_trim=False,
                    )

                optimize_kwargs.setdefault("strip_bytecode", False)
                optimize_kwargs.setdefault("strip_dist_info", False)

                stats = optimize_bundle(
                    layout,
                    remove_packages=unused_packages or None,
                    **optimize_kwargs,
                )
                typer.echo(
                    " - removed "
                    f"{stats.files_removed} files, {stats.directories_removed} directories, "
                    f"{stats.packages_removed} packages, reclaimed {stats.bytes_reclaimed} bytes"
                )

            typer.echo("Freezing bytecode and metadata")
            pyz = finalize_bytecode_bundle(
                layout,
                build_pyz=config.zip_imports,
                freeze_metadata=config.freeze_metadata,
                strip_sources=config.strip_sources,
                block_packaging=config.block_packaging,
            )
            if pyz:
                typer.echo(f" - bundle.pyz created at: {pyz}")

            if config.output_format == "directory":
                typer.echo("🚀 Finalizing directory bundle")
                launcher = finalize_directory_bundle(
                    layout,
                    entrypoint=config.entrypoint,
                    output_name="run",
                )
                typer.echo("Build complete!")
                typer.echo(f"Run with: {launcher}")

            elif config.output_format == "singlefile":
                typer.echo("🚀 Finalizing single-file bundle")
                artifact = finalize_singlefile_bundle(
                    layout,
                    output_file=Path(output),
                )
                typer.echo("Build complete!")
                typer.echo(f"Archive created at: {artifact}")

            else:  
                typer.echo("Finalizing squashfs bundle")
                artifact = finalize_squashfs_bundle(
                    layout,
                    output_file=Path(output),
                )
                typer.echo("Build complete!")
                typer.echo(f"Image created at: {artifact}")

    except ShrinkwrapError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        sys.exit(exc.exit_code)


@app.command(hidden=True)
def run():
    typer.echo("Run command not implemented yet.")
    sys.exit(1)

def run_cli() -> None:
    app()


if __name__ == "__main__":
    run_cli()
