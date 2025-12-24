from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from shrinkwrap.errors import PythonRuntimeError


class PythonRuntime(BaseModel):
    python_executable: Path = Field(
        ...,
        description="Path to the Python interpreter binary",
    )

    version: str = Field(
        ...,
        description="Python version string (e.g. 3.11.7)",
    )

    stdlib_path: Path = Field(
        ...,
        description="Path to the Python standard library",
    )

    libpython_path: Optional[Path] = Field(
        default=None,
        description="Path to libpython shared library (if applicable)",
    )

    @field_validator("python_executable")
    @classmethod
    def validate_python_executable(cls, value: Path) -> Path:
        if not value.exists():
            raise PythonRuntimeError(
                f"Python executable does not exist: {value}"
            )
        if not value.is_file():
            raise PythonRuntimeError(
                f"Python executable is not a file: {value}"
            )
        return value

    @field_validator("stdlib_path")
    @classmethod
    def validate_stdlib_path(cls, value: Path) -> Path:
        if not value.exists():
            raise PythonRuntimeError(
                f"Standard library path does not exist: {value}"
            )
        if not value.is_dir():
            raise PythonRuntimeError(
                f"Standard library path is not a directory: {value}"
            )
        return value

    @field_validator("libpython_path")
    @classmethod
    def validate_libpython_path(
        cls, value: Optional[Path]
    ) -> Optional[Path]:
        if value is None:
            return value

        if not value.exists():
            raise PythonRuntimeError(
                f"libpython not found at: {value}"
            )
        if not value.is_file():
            raise PythonRuntimeError(
                f"libpython path is not a file: {value}"
            )
        return value

    @property
    def major_minor(self) -> str:
        parts = self.version.split(".")
        return ".".join(parts[:2])

    @property
    def is_embeddable(self) -> bool:
        return self.libpython_path is not None

    class Config:
        frozen = True
