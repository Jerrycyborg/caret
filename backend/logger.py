"""Central logging setup for the Caret backend sidecar.

Log file location:
  - Packaged (Windows): %APPDATA%\Caret\logs\caret-backend.log
  - Dev:                ./logs/caret-backend.log

Call setup_logging() once at startup. All modules then use:
    import logging
    log = logging.getLogger(__name__)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def _log_dir() -> Path:
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        return Path(appdata) / "Caret" / "logs"
    return Path("logs")


def log_path() -> Path:
    return _log_dir() / "caret-backend.log"


def setup_logging(level: int = logging.INFO) -> None:
    log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_dir / "caret-backend.log",
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Quiet noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
