# Shrinkwrap (Beta)

Shrinkwrap packages FastAPI (or any ASGI) applications into self-contained, redistributable directories that ship with a Python interpreter, your code, dependencies, and a launcher script. Bundle once, copy to any compatible host, and run without system Python.

## Features

- Discovers the local Python 3.11 runtime and copies the stdlib, shared `libpython`, and optional `pythonXY.zip` archive.
- Installs application dependencies (plus transitives) into an isolated `site-packages` tree.
- Copies your project sources while excluding previously built bundles to avoid recursion.
- Generates an executable launcher that sets `PYTHONHOME`, `PYTHONPATH`, and invokes Uvicorn with your entry point.

## Prerequisites

- macOS or Linux host
- Python 3.11 available on `PATH` as `python3`
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

Start the bundled app:

```bash
./dist/myapp/run
```

## CLI Reference

| Command | Description |
| --- | --- |
| `shrinkwrap analyze --entry app.main:app` | Validates the entry point exports an ASGI app. |
| `shrinkwrap build --entry app.main:app --output dist/myapp` | Produces a runnable bundle at the given path. |

Append `--verbose` to surface additional diagnostics.

## Development Workflow

1. Create/activate a virtual environment and install with `pip install -e .`.
2. Run tests (if present) with `pytest` before sending pull requests.
3. Keep `pyproject.toml` and `shrinkwrap/__init__.py` versions aligned.
4. Format/ lint using your preferred tooling before opening a PR.

## License

MIT License
