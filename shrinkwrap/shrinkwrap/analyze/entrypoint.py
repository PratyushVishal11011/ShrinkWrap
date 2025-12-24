import importlib
from typing import Tuple

from fastapi import FastAPI

from shrinkwrap.errors import EntrypointError


def parse_entrypoint(entrypoint: str) -> Tuple[str, str]:
    if ":" not in entrypoint:
        raise EntrypointError(
            "Entrypoint must be in the format 'module:attribute'"
        )

    module_path, attribute = entrypoint.split(":", 1)

    if not module_path or not attribute:
        raise EntrypointError(
            "Entrypoint must specify both module and attribute"
        )

    return module_path, attribute


def import_module(module_path: str):
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        raise EntrypointError(
            f"Module '{module_path}' could not be found"
        ) from exc
    except ImportError as exc:
        raise EntrypointError(
            f"Failed to import module '{module_path}': {exc}"
        ) from exc


def analyze_entrypoint(entrypoint: str) -> FastAPI:
    module_path, attribute = parse_entrypoint(entrypoint)

    module = import_module(module_path)

    if not hasattr(module, attribute):
        raise EntrypointError(
            f"Module '{module_path}' has no attribute '{attribute}'"
        )

    app = getattr(module, attribute)

    if not isinstance(app, FastAPI):
        raise EntrypointError(
            f"Attribute '{attribute}' is not a FastAPI application instance"
        )

    return app
