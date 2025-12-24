class ShrinkwrapError(Exception):
    exit_code: int = 1

    def __init__(self, message: str):
        super().__init__(message)

class ConfigError(ShrinkwrapError):
    exit_code = 2


class EntrypointError(ShrinkwrapError):
    exit_code = 3


class RequirementsError(ShrinkwrapError):
    exit_code = 4

class EnvironmentError(ShrinkwrapError):
    exit_code = 10


class PythonRuntimeError(ShrinkwrapError):
    exit_code = 11

class BuildError(ShrinkwrapError):
    exit_code = 20


class BundleFormatError(BuildError):
    exit_code = 21
