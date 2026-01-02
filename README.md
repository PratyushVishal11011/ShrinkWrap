# Shrinkwrap (Beta)

Shrinkwrap packages FastAPI (or any ASGI) applications into self-contained, redistributable directories that ship with a Python interpreter, your code, dependencies, and a launcher script. Bundle once, copy to any compatible host, and run without system Python.

## Features

- Discovers the local Python 3.10-3.12 runtime and copies the stdlib, shared `libpython`, and optional `pythonXY.zip` archive.
- Installs application dependencies (plus transitives) into an isolated `site-packages` tree.
- Copies your project sources while excluding previously built bundles to avoid recursion.
- Precompiles app + dependencies to `.pyc`, optionally packs them into `bundle.pyz`, and drops `.py` sources by default.
- Generates an executable launcher that sets `PYTHONHOME`, `PYTHONPATH`, and invokes Uvicorn with your entry point while disabling `pip`/`ensurepip`.
- Prunes unused dependency packages based on your app's import graph (can be disabled with `--no-prune-unused`).
- Strips common weight (bytecode, tests, docs, type hints, packaging tools) to shrink the bundle size (toggle with `--no-optimize`).

## Prerequisites

- macOS or Linux host
- Python 3.10-3.12 available on `PATH` as `python3`
- `pip` for dependency installation

## Getting Started

Clone the repository and install in editable mode (recommended when developing locally):

```bash
git clone https://github.com/PratyushVishal11011/Shrinkwrap.git
cd shrinkwrap
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

Run the CLI from your project root:

```bash
shrinkwrap build --entry app.main:app --output dist/myapp
```

This command:

1. Discovers the active Python runtime.
2. Reads `requirements.txt` (and `requirements-dev.txt` if present) to install dependencies.
3. Copies your source tree, runtime, and dependencies into `dist/myapp`.
4. Writes `dist/myapp/run`, an executable launcher.
5. Prunes unused dependencies and strips non-essential files by default.

You can choose other output formats:

```bash
# tar.gz archive
shrinkwrap build --entry app.main:app --format singlefile --output dist/myapp.tar.gz

# SquashFS image (requires mksquashfs on PATH)
shrinkwrap build --entry app.main:app --format squashfs --output dist/myapp.sqsh

# Self-extracting executable (macOS/Linux/Windows)
shrinkwrap build --entry app.main:app --format executable --output dist/myapp
```

Start the bundled app:

```bash
./dist/myapp/run
# or for executable format
./dist/myapp
# on Windows
dist\myapp.bat
```

## CLI Reference

| Command | Description |
| --- | --- |
| `shrinkwrap analyze --entry app.main:app` | Validates the entry point exports an ASGI app. |
| `shrinkwrap build --entry app.main:app --output dist/myapp [--format directory|singlefile|squashfs|executable] [--no-optimize] [--no-prune-unused] [--keep-package pkg] [--drop-package pkg] [--no-zip-imports] [--keep-sources] [--no-freeze-metadata] [--allow-packaging]` | Produces a bundle in the chosen format at the given path, with optional pruning/optimization controls. |

### Output formats

- **directory** (default): runnable directory with `run` launcher.
- **singlefile**: tar.gz (or zip if you pass a `.zip` output name) archive of the directory layout.
- **squashfs**: SquashFS image (needs `mksquashfs` installed and on PATH).
- **executable**: self-extracting executable that unpacks to a temp dir and runs the bundled launcher (`run` on POSIX, `run.bat` on Windows).

Append `--verbose` to surface additional diagnostics.

### Pruning and optimization flags

- `--prune-unused/--no-prune-unused` (default on): remove dependency packages that are not imported by your app.
- `--keep-package PKG`: force-keep a package even if unused (repeatable).
- `--drop-package PKG`: force-remove a package even if it appears used (repeatable).
- `--optimize/--no-optimize` (default on): controls stripping bytecode, tests, docs, type hints, packaging tools, etc.
- `--zip-imports/--no-zip-imports` (default on): build `bundle.pyz` and prepend it to `PYTHONPATH`.
- `--strip-sources/--keep-sources` (default strip): remove `.py` after emitting `.pyc`.
- `--freeze-metadata/--no-freeze-metadata` (default on): write a frozen `importlib.metadata` snapshot to skip filesystem scanning.
- `--block-packaging/--allow-packaging` (default block): install a runtime shim that raises on `pip`/`ensurepip` imports and sets `PYTHONZIPIMPORT_USE_ZIPFILE`/`PYTHONDONTWRITEBYTECODE`.

## Development Workflow

1. Create/activate a virtual environment and install with `pip install -e .`.
2. Run tests (if present) with `pytest` before sending pull requests.
3. Keep `pyproject.toml` and `shrinkwrap/__init__.py` versions aligned.
4. Format/ lint using your preferred tooling before opening a PR.

## License

MIT License
