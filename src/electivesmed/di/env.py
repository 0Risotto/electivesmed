"""Environment loading from .env (does not override existing variables)."""

import os
from pathlib import Path

from ..paths import ENV_PATH


def load_env_file(path: Path | None = None) -> None:
    env_path = Path(path) if path else ENV_PATH
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))
