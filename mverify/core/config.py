from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class AppConfig:
    data_dir: Path
    database_path: Path
    log_dir: Path


def load_config() -> AppConfig:
    base = Path(os.environ.get("MVERIFY_HOME", Path.home() / ".mverify")).expanduser()
    data_dir = base / "data"
    log_dir = base / "logs"
    data_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    return AppConfig(
        data_dir=data_dir,
        database_path=data_dir / "mverify.sqlite3",
        log_dir=log_dir,
    )
