from pathlib import Path
import os

import uvicorn


def _configure_runtime() -> None:
    home = Path.home()
    oxy_root = home / ".oxy"
    oxy_root.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("OXY_DB_PATH", str(oxy_root / "oxy.db"))


def main() -> None:
    _configure_runtime()
    from main import app

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
