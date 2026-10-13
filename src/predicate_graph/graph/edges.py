"""Load extraction into `edges` DB table"""

import sqlite3
from pathlib import Path

from predicate_graph.config import NODES_DB
from predicate_graph.extract.run import load_cached
from predicate_graph.graph.validate import validate_extractions, summarize
from predicate_graph.graph.match import resolve_extractions, summarize as summarize_matches

def build_edges(extractions_path: Path) -> None:
    extractions = list(load_cached(extractions_path).values())
    results = validate_extractions(extractions)

    conn = sqlite3.connect(NODES_DB)
    conn.execute("DELETE FROM edges")

    conn.executemany(
        "INSERT OR IGNORE INTO edges (citing, predicate, valid, citing_date, predicate_date, page, quote) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(r.citing, r.predicate, int(r.ok), r.citing_date, r.predicate_date, r.page, r.quote) for r in results],
    )
    conn.commit()
    conn.close()

    summarize(results)

def build_edges_name_only(extractions_path: Path, requested: set[str]) -> None:
    extractions = load_cached(extractions_path)
    matches = resolve_extractions(list(extractions.values()))

    # remove unresolved matches
    resolved = [m for m in matches if m.resolved]

    conn = sqlite3.connect(NODES_DB)
    conn.execute("DELETE FROM edges_name_only")

    conn.executemany(
        "INSERT OR IGNORE INTO edges_name_only (citing, predicate, score, citing_date, predicate_date, page, quote) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(m.citing, m.resolved_k_number, m.score, m.citing_date, m.predicate_date, m.page, m.quote) for m in resolved]
    )
    conn.commit()
    conn.close()
    summarize_matches(matches, extractions, requested)