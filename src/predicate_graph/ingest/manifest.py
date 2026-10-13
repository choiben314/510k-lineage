from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from predicate_graph.config import MANIFEST, RAW

def sha256_file(path: Path, chunk_size: int=1<<20) -> str:
    """Hash a file in 1 MB chunks.

    Streaming rather than path.read_bytes() because these partitions run to
    hundreds of megabytes and we should never need to hold one in memory.
    """

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()

def record_fetch(
        url: str,
        dest: Path,
        sha256: str,
        n_bytes: int,
        export_date: str | None = None,
) -> None:
    """Append one provenance line."""
    entry = {
        "url": url,
        "dest": str(dest.relative_to(RAW)),
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sha256": sha256,
        "bytes": n_bytes,
        "export_date": export_date,
    }
    with MANIFEST.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")

def load_manifest() -> dict[str, dict]:
    """Return the latest entry per destination path.
    
    Later lines win, so a re-download supersedes an earlier record without
    us ever having to edit or delete a line."""

    if not MANIFEST.exists():
        return {}
    entries: dict[str, dict] = {}
    with MANIFEST.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            entries[entry["dest"]] = entry
    return entries