import sys
import typer

from shrinkwrap.analyze.entrypoint import analyze_entrypoint
from shrinkwrap.errors import ShrinkwrapError
from shrinkwrap.logger import setup_logger
from pathlib import Path

from shrinkwrap.config import BuildConfig
from shrinkwrap.analyze.requirements import discover_requirements
from shrinkwrap.runtime.discover import discover_python_runtime
from shrinkwrap.runtime.env import build_runtime_env
from shrinkwrap.bundle.assembler import assemble_bundle
from shrinkwrap.bundle.formats.directory import finalize_directory_bundle
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
):

    try:
        typer.echo("Building Shrinkwrap bundle")

        config = BuildConfig(entrypoint=entry)

        typer.echo("Discovering Python runtime")
        runtime = discover_python_runtime()

        typer.echo("Discovering dependencies")
        requirements = discover_requirements(config.project_root)

        with temp_dir() as deps_dir:
            typer.echo("Installing dependencies")
            site_packages = install_dependencies(
                python_executable=runtime.python_executable,
                requirements=requirements,
                output_dir=deps_dir / "site-packages",
            )

            typer.echo("Assembling bundle")
            app_dir = config.project_root / "app"
            if not app_dir.exists():
                raise ShrinkwrapError(
                    "Expected application code in ./app directory"
                )

            layout = assemble_bundle(
                config=config,
                runtime=runtime,
                app_sources=[app_dir],
                dependencies_dir=site_packages,
                output_dir=Path(output),
            )

        typer.echo("Finalizing directory bundle")
        launcher = finalize_directory_bundle(
            layout,
            entrypoint=config.entrypoint,
            output_name="run",
        )

        typer.echo(f"Build complete!")
        typer.echo(f"Run with: {launcher}")

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
