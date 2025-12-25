from pathlib import Path
from dataclasses import dataclass
from typing import Literal

@dataclass(frozen=True)
class BundleLayout:
    root: Path
    stdlib_relative: Path = Path("lib/python")
    platform: Literal["posix", "windows"] = "posix"

    @property
    def runtime_dir(self) -> Path:
        return self.root / "runtime"

    @property
    def app_dir(self) -> Path:
        return self.root / "app"

    @property
    def site_packages_dir(self) -> Path:
        return self.root / "site-packages"

    @property
    def metadata_dir(self) -> Path:
        return self.root / "meta"

    @property
    def python_executable(self) -> Path:
        if self.is_windows:
            return self.runtime_dir / "python.exe"
        return self.runtime_dir / "bin" / "python"

    @property
    def stdlib_dir(self) -> Path:
        return self.runtime_dir / self.stdlib_relative

    @property
    def libpython_dir(self) -> Path:
        if self.is_windows:
            return self.runtime_dir
        return self.runtime_dir / "lib"

    @property
    def python_zip_dir(self) -> Path:
        if self.is_windows:
            return self.runtime_dir
        return self.runtime_dir / "lib"

    @property
    def dlls_dir(self) -> Path:
        if self.is_windows:
            return self.runtime_dir / "DLLs"
        return self.stdlib_dir / "lib-dynload"

    @property
    def runtime_metadata(self) -> Path:
        return self.metadata_dir / "runtime.json"

    @property
    def build_metadata(self) -> Path:
        return self.metadata_dir / "build.json"

    def all_dirs(self) -> list[Path]:
        dirs = [
            self.root,
            self.runtime_dir,
            self.python_executable.parent,
            self.stdlib_dir.parent,
            self.libpython_dir,
            self.app_dir,
            self.site_packages_dir,
            self.metadata_dir,
        ]

        if self.is_windows:
            dirs.append(self.dlls_dir)
        else:
            dirs.append(self.runtime_dir / "lib")

        unique: list[Path] = []
        seen: set[Path] = set()
        for directory in dirs:
            if directory in seen:
                continue
            seen.add(directory)
            unique.append(directory)
        return unique

    @property
    def is_windows(self) -> bool:
        return self.platform == "windows"
