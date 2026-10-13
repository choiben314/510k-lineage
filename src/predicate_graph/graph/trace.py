"""Derives lineage for a given k-number device with good old-fashioned iterative BFS."""
from collections import deque
from pathlib import Path

from predicate_graph.extract.schema import Extraction
from predicate_graph.extract.run import extract_k_numbers
from predicate_graph.graph.validate import validate_extractions, summarize

def trace(model_key: str, seeds: list[str], out_path: Path) -> dict[str, Extraction]:

    visited = set(seeds)
    queue = deque(seeds)

    all_results = {}

    while queue:
        level = list(queue)
        queue.clear()

        print(f"Found {len(level)} nodes to explore.")

        extractions = extract_k_numbers(model_key, level, out_path)
        all_results.update(extractions)

        extraction_list = list(extractions.values())

        results = validate_extractions(extraction_list)
        summarize(results)

        for result in results:
            if not result.ok:
                continue
            if result.predicate in visited:
                continue
            visited.add(result.predicate)
            queue.append(result.predicate)

    return all_results