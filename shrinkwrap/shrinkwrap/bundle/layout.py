from pathlib import Path
from dataclasses import dataclass

@dataclass(frozen=True)
class BundleLayout:
    root: Path

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
        return self.runtime_dir / "bin" / "python"

    @property
    def stdlib_dir(self) -> Path:
        return self.runtime_dir / "lib" / "python"

    @property
    def libpython_dir(self) -> Path:
        return self.runtime_dir / "lib"

    @property
    def runtime_metadata(self) -> Path:
        return self.metadata_dir / "runtime.json"

    @property
    def build_metadata(self) -> Path:
        return self.metadata_dir / "build.json"

    def all_dirs(self) -> list[Path]:
        return [
            self.root,
            self.runtime_dir,
            self.runtime_dir / "bin",
            self.runtime_dir / "lib",
            self.app_dir,
            self.site_packages_dir,
            self.metadata_dir,
        ]
