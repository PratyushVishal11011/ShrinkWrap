import ast
import sys
from pathlib import Path
from typing import Dict, Set

class ImportGraph:
    def __init__(self) -> None:
        self.graph: Dict[str, Set[str]] = {}

    def add_module(self, module: str) -> None:
        self.graph.setdefault(module, set())

    def add_edge(self, source: str, target: str) -> None:
        self.add_module(source)
        self.graph[source].add(target)

    def dependencies_of(self, module: str) -> Set[str]:
        return self.graph.get(module, set())

    def all_modules(self) -> Set[str]:
        return set(self.graph.keys())

def build_import_graph(
    entry_module: str,
    project_root: Path,
) -> ImportGraph:

    graph = ImportGraph()
    visited: Set[str] = set()

    _walk_module(
        module=entry_module,
        project_root=project_root,
        graph=graph,
        visited=visited,
    )

    return graph

def _walk_module(
    module: str,
    project_root: Path,
    graph: ImportGraph,
    visited: Set[str],
) -> None:
    if module in visited:
        return

    visited.add(module)
    graph.add_module(module)

    source_path = _module_to_path(module, project_root)
    if source_path is None:
        return

    try:
        source = source_path.read_text()
    except OSError:
        return

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return

    for imported in _extract_imports(tree):
        graph.add_edge(module, imported)

        if _is_local_module(imported, project_root):
            _walk_module(
                module=imported,
                project_root=project_root,
                graph=graph,
                visited=visited,
            )


def _extract_imports(tree: ast.AST) -> Set[str]:
    imports: Set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])

        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module.split(".")[0])

    return imports


def _module_to_path(module: str, project_root: Path) -> Path | None:
    relative = Path(*module.split("."))

    file_path = project_root / f"{relative}.py"
    if file_path.exists():
        return file_path

    init_path = project_root / relative / "__init__.py"
    if init_path.exists():
        return init_path

    return None


def _is_local_module(module: str, project_root: Path) -> bool:
    return _module_to_path(module, project_root) is not None


def is_stdlib_module(module: str) -> bool:
    return module in sys.builtin_module_names
