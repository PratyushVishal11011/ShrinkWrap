import logging
import sys


def setup_logger(verbose: bool = False) -> None:
    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    level = logging.DEBUG if verbose else logging.INFO

    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter(
        fmt="[%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)

    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)