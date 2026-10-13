from __future__ import annotations

import json
import zipfile

from predicate_graph.config import RAW

def peek(endpoint: str, n: int=1, max_chars: int = 8000) -> None:
    """Pretty-print the first n records of an endpoint's first partition
    
    Loads one partition fully into memory. Fine for inspection; the
    real loaders will need to be more careful with the larger endpoints.
    """

    partitions = sorted((RAW / endpoint).glob("*.json.zip"))

    if not partitions:
        raise SystemExit(f"no partitions for {endpoint!r}")

    with zipfile.ZipFile(partitions[0]) as archive:
        inner_name = archive.namelist()[0]
        with archive.open(inner_name) as handle:
            payload = json.load(handle)

    results = payload["results"]
    print(f"# {endpoint}: {len(results):,} records in {partitions[0].name}")
    print(f"# top-level keys of record 0: {sorted(results[0].keys())}")
    print(json.dumps(results[:n], indent=2)[:max_chars])
