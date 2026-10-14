"""Persistent, bounded diagnostic logs for background crawl jobs."""
from datetime import datetime, timezone
from pathlib import Path
import threading
from .core import DATA

_guard = threading.RLock()
MAX_READ = 500_000

def log_path(job_id: int, data: Path = DATA) -> Path:
    return data / "logs" / f"job_{int(job_id)}.log"

def write(job_id: int, level: str, message: str, data: Path = DATA) -> None:
    path = log_path(job_id, data)
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _guard, path.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp} [{level.upper()}] {message}\n")

def read(job_id: int, data: Path = DATA) -> str:
    path = log_path(job_id, data)
    if not path.is_file():
        return "Für diesen Job ist keine Logdatei vorhanden."
    with path.open("rb") as stream:
        stream.seek(0, 2)
        length = stream.tell()
        stream.seek(max(0, length - MAX_READ))
        content = stream.read()
    return ("[Nur die letzten 500 KB angezeigt]\n" if length > MAX_READ else "") + content.decode("utf-8", "replace")
