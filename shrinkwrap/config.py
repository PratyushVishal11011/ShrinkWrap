from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, field_validator

from shrinkwrap.errors import ConfigError


class BuildConfig(BaseModel):
    entrypoint: str = Field(
        ...,
        description="ASGI entrypoint in the form module:attribute",
        examples=["app.main:app"],
    )

    project_root: Path = Field(
        default=Path.cwd(),
        description="Root directory of the FastAPI project",
    )

    output_name: str = Field(
        default="shrinkwrapped-app",
        description="Name of the output executable",
    )
    optimize: bool = Field(
        default=True,
        description="Remove bytecode, tests, and other non-essential files",
    )
    prune_unused: bool = Field(
        default=True,
        description="Remove dependencies that are not imported by the application",
    )
    zip_imports: bool = Field(
        default=True,
        description="Package application and dependencies into bundle.pyz and prefer zipimport",
    )
    strip_sources: bool = Field(
        default=True,
        description="Remove .py sources after byte-compiling to .pyc",
    )
    freeze_metadata: bool = Field(
        default=True,
        description="Freeze importlib.metadata data to avoid filesystem scans",
    )
    block_packaging: bool = Field(
        default=True,
        description="Disable pip/ensurepip inside the bundled runtime",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug behavior in the build",
    )

    output_format: Literal["directory", "singlefile", "squashfs", "executable"] = Field(
        default="directory",
        description="Bundle output format",
    )
    @field_validator("entrypoint")
    @classmethod
    def validate_entrypoint_format(cls, value: str) -> str:
        if ":" not in value:
            raise ConfigError(
                "Entrypoint must be in the format 'module:attribute'"
            )
        return value

    @field_validator("project_root")
    @classmethod
    def validate_project_root(cls, value: Path) -> Path:
        if not value.exists():
            raise ConfigError(f"Project root does not exist: {value}")
        if not value.is_dir():
            raise ConfigError(f"Project root is not a directory: {value}")
        return value

    @field_validator("output_name")
    @classmethod
    def validate_output_name(cls, value: str) -> str:

        if not value:
            raise ConfigError("Output name cannot be empty")
        if "/" in value or "\\" in value:
            raise ConfigError("Output name must not contain path separators")
        return value

    def entrypoint_module(self) -> str:
        return self.entrypoint.split(":", 1)[0]

    def entrypoint_attribute(self) -> str:
        return self.entrypoint.split(":", 1)[1]

    class Config:
        frozen = True
