import sqlite3
from dataclasses import dataclass

from predicate_graph.config import NODES_DB
from predicate_graph.extract.schema import Extraction

@dataclass
class ValidationResult:
    citing: str
    predicate: str
    exists: bool
    citing_date: str | None
    predicate_date: str | None
    date_order_ok: bool | None
    page: int
    quote: str

    @property
    def ok(self) -> bool:
        return self.exists and self.date_order_ok is not False

def _load_decision_dates(conn: sqlite3.Connection, k_numbers: set[str]) -> dict[str, str]:
    if not k_numbers:
        return {}
    placeholders = ",".join("?" * len(k_numbers))
    rows = conn.execute(
        f"SELECT k_number, decision_date FROM nodes WHERE k_number IN ({placeholders})",
        list(k_numbers),
    ).fetchall()
    return dict(rows)

def validate_edges(edges: list[tuple[str, str, int, str]]) -> list[ValidationResult]:
    """edges: (citing_k_number, predicate_k_number) pairs."""
    conn = sqlite3.connect(NODES_DB)
    dates = _load_decision_dates(conn, {e[0] for e in edges} | {e[1] for e in edges})
    conn.close()

    results = []
    for citing, predicate, page, quote in edges:
        citing_date = dates.get(citing)
        predicate_date = dates.get(predicate)
        date_order_ok = predicate_date <= citing_date if (predicate_date and citing_date) else None

        results.append(
            ValidationResult(
                citing=citing,
                predicate=predicate,
                exists=predicate in dates,
                citing_date=citing_date,
                predicate_date=predicate_date,
                date_order_ok=date_order_ok,
                page=page,
                quote=quote
            )
        )

    return results

def validate_extractions(extractions: list[Extraction]) -> list[ValidationResult]:
    """Extract edges and run basic, deterministic validation"""
    edges = [(e.k_number, p.k_number, p.page, p.quote) for e in extractions for p in e.predicates]
    return validate_edges(edges)

def summarize(results: list[ValidationResult]) -> None:
    missing = [r for r in results if not r.exists]
    invalid_order = [r for r in results if r.date_order_ok is False]

    print(f"\n===Summary===\n\
        Across {len(results)} edges, there were:\n\
        Missing: {len(missing)}\n\
        Invalid Date Ordering: {len(invalid_order)}"
    )