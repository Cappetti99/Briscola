"""Small helpers shared by the local JSON stores."""

import shutil
from pathlib import Path


def backup_once(path: Path, suffix: str) -> Path:
    """Keep the first pre-migration file next to the active store."""
    backup = path.with_name(path.name + suffix)
    if path.exists() and not backup.exists():
        shutil.copy2(path, backup)
    return backup
