from __future__ import annotations

from pathlib import Path

import httpx

from predicate_graph.config import RAW
from predicate_graph.ingest.manifest import load_manifest, record_fetch, sha256_file
from predicate_graph.ingest.documents import UA

DOWNLOAD_INDEX = "https://api.fda.gov/download.json"

ENDPOINTS = ("510k", "recall", "enforcement", "registrationlisting")

def fetch_index(client: httpx.Client) -> dict:
    """Fetch openFDA's machine-readable index of every bulk partition"""
    response = client.get(DOWNLOAD_INDEX)
    response.raise_for_status()
    return response.json()

def partitions_for(index: dict, endpoint: str) -> tuple[str, int, list[dict]]:
    """Pull (export_date, total_records, partitions) for one device endpoint"""
    node = index["results"]["device"][endpoint]
    return node["export_date"], node["total_records"], node["partitions"]

def download_file(client: httpx.Client, url: str, dest: Path) -> int:
    """Stream a URL to disk, returning bytes written.
    
    Writes to dest.part and renames on success. rename() is atomic on POSIX, so a killed processed
    leaves a .part file rather than a truncated .json.zip that looks complete.
    """

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    n_bytes = 0
    with client.stream("GET", url, follow_redirects=True) as response:
        response.raise_for_status()
        with tmp.open("wb") as handle:
            for chunk in response.iter_bytes(chunk_size=1<<20):
                handle.write(chunk)
                n_bytes += len(chunk)
    tmp.rename(dest)
    return n_bytes

def sync(endpoints: tuple[str, ...] = ENDPOINTS) -> None:
    """Idempotently bring data/raw up to date with openFDA's bulk exports."""

    manifest = load_manifest()
    headers = {"User-Agent": UA}

    with httpx.Client(timeout=60.0, headers=headers) as client:
        index = fetch_index(client)

        for endpoint in endpoints:
            export_date, total_records, partitions = partitions_for(index, endpoint)
            print(
                f"{endpoint}: export_date={export_date} "
                f"total_records={total_records:,} partitions={len(partitions)}"
            )

            for partition in partitions:
                url = partition["file"]
                dest = RAW / endpoint / url.rsplit("/", 1)[-1]
                key = str(dest.relative_to(RAW))

                recorded = manifest.get(key)
                if dest.exists() and recorded and recorded["sha256"] == sha256_file(dest):
                    print(f" skip {dest.name}")
                    continue

                n_bytes = download_file(client, url, dest)
                record_fetch(url, dest, sha256_file(dest), n_bytes, export_date)

                print(f" got {dest.name} ({n_bytes / 1e6:.1f} MB)")