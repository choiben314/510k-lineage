from __future__ import annotations

import json
import zipfile
from collections.abc import Iterator
from datetime import datetime

from predicate_graph.config import RAW

def iter_records(endpoint: str, metas: list[dict] | None = None) -> Iterator[dict]:
    """Yield every record across all partitions of an endpoint."""

    partitions = sorted((RAW / endpoint).glob("*.json.zip"))

    if not partitions:
        raise SystemExit(f"No partitions in {endpoint!r}")

    for partition in partitions:
        with zipfile.ZipFile(partition) as archive:
            inner = archive.namelist()[0]
            with archive.open(inner) as handle:
                payload = json.load(handle)

        if metas is not None:
            meta = payload.get("meta") or {}
            counts = meta.get("results") or {}
            metas.append(
                {
                    "partition": partition.name,
                    "last_updated": meta.get("last_updated"),
                    "total": counts.get("total"),
                    "limit": counts.get("limit"),
                }
            )
        yield from payload['results']

def iso_date(value: str | None) -> str | None:
    """Normalize dates to ISO YYYY-MM-DD"""

    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def chunked(iterable, size: int = 10_000):
    """Batch an iterable so executemany gets useful-sized chunks"""

    if size <= 0:
        return

    batch = []
    for item in iterable:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch