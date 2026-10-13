import sqlite3
from predicate_graph.config import NODES_DB

def select_targets(
        since: str | None = None,
        until: str | None = None,
        limit: int | None = None
) -> list[str]:
    query = "SELECT k_number FROM nodes WHERE statement_or_summary = 'Summary'"
    params: list = []

    if since:
        query += " AND decision_date >= ?"
        params.append(since)

    if until:
        query += " AND decision_date <= ?"
        params.append(until)

    query += " ORDER BY k_number"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    conn = sqlite3.connect(NODES_DB)
    k_numbers = [k for (k,) in conn.execute(query, params)]
    conn.close()
    return k_numbers