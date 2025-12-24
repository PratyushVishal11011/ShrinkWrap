from pathlib import Path
from typing import List

from shrinkwrap.errors import RequirementsError


SUPPORTED_FILES = (
    "requirements.txt",
    "requirements-dev.txt",
)


def discover_requirements(project_root: Path) -> List[str]:
    requirements: List[str] = []

    found_any = False

    for filename in SUPPORTED_FILES:
        path = project_root / filename
        if path.exists():
            found_any = True
            requirements.extend(_parse_requirements_file(path))

    if not found_any:
        raise RequirementsError(
            "No supported dependency files found "
            "(expected requirements.txt or requirements-dev.txt)"
        )

    if not requirements:
        raise RequirementsError(
            "Dependency files were found but contained no dependencies"
        )

    return _normalize(requirements)


def _parse_requirements_file(path: Path) -> List[str]:
    dependencies: List[str] = []

    try:
        content = path.read_text()
    except OSError as exc:
        raise RequirementsError(
            f"Failed to read dependency file: {path}"
        ) from exc

    for line in content.splitlines():
        line = line.strip()

        # Ignore comments and blank lines
        if not line or line.startswith("#"):
            continue

        # Ignore pip directives for now
        if line.startswith("-"):
            continue

        dependencies.append(line)

    return dependencies


def _normalize(dependencies: List[str]) -> List[str]:
    seen = set()
    normalized: List[str] = []

    for dep in dependencies:
        dep = dep.strip()
        if dep and dep not in seen:
            seen.add(dep)
            normalized.append(dep)

    return normalized
