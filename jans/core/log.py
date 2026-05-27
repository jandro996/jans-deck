import logging
import sys
from pathlib import Path

JANS_DIR = Path.home() / ".jans"
LOG_FILE = JANS_DIR / "jans.log"


def setup_logging() -> logging.Logger:
    JANS_DIR.mkdir(exist_ok=True)

    logger = logging.getLogger("jans")
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


log = setup_logging()
