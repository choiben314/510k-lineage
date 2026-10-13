from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from predicate_graph.config import NODES_DB, load_sql
from predicate_graph.ingest.records import chunked, iso_date, iter_records

KNOWN_510K_KEYS = {
    "k_number", "device_name", "applicant", "decision_date", "date_received",
    "decision_code", "decision_description", "product_code",
    "statement_or_summary", "clearance_type", "third_party_flag",
    "expedited_review_flag", "advisory_committee",
    "advisory_committee_description", "review_advisory_committee",
    "openfda", "address_1", "address_2", "city", "state", "country_code",
    "zip_code", "postal_code", "contact",
}

def _fmt(n) -> str:
    return f"{n:,}" if isinstance(n, int) else "?"

def set_meta(conn: sqlite3.Connection, key: str, value) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", (key, str(value))
    )

def record_source_meta(conn: sqlite3.Connection, endpoint: str, metas: list[dict]) -> int | None:
    """Persist the dataset version and declared record count from the files themselves."""
    if not metas:
        return None

    totals = {m["total"] for m in metas if m["total"] is not None}
    declared = max(totals) if totals else None
    partition_sum = sum(m["limit"] or 0 for m in metas)
    last_updated = max((m["last_updated"] for m in metas if m["last_updated"]), default=None)

    set_meta(conn, f"last_updated.{endpoint}", last_updated)
    set_meta(conn, f"declared_total.{endpoint}", declared)

    if len(totals) > 1:
        print(f"  WARNING {endpoint}: partitions disagree on total: {sorted(totals)}")
    if declared is not None and partition_sum != declared:
        print(
            f"  WARNING {endpoint}: partition limits sum to {partition_sum:,}, "
            f"file declares {declared:,} -- a partition may be missing"
        )
    return declared

def load_nodes(conn: sqlite3.Connection) -> None:
    unmapped: set[str] = set()
    metas: list[dict] = []
    raw_count = 0

    def rows():
        nonlocal raw_count
        for record in iter_records("510k", metas):
            raw_count += 1
            unmapped.update(set(record.keys()) - KNOWN_510K_KEYS)
            openfda = record.get("openfda") or {}
            yield (
                record["k_number"],
                record.get("device_name"),
                record.get("applicant"),
                iso_date(record.get("decision_date")),
                iso_date(record.get("date_received")),
                record.get("decision_code"),
                record.get("decision_description"),
                record.get("product_code"),
                record.get("statement_or_summary"),
                record.get("clearance_type"),
                record.get("third_party_flag"),
                record.get("expedited_review_flag"),
                record.get("advisory_committee"),
                record.get("advisory_committee_description"),
                openfda.get("regulation_number"),
                openfda.get("device_class"),
                openfda.get("medical_specialty_description"),
                record.get("state"),
                record.get("country_code"),
            )

    sql = """
        INSERT OR IGNORE INTO nodes_raw (
            k_number, device_name, applicant, decision_date, date_received,
            decision_code, decision_description, product_code,
            statement_or_summary, clearance_type, third_party_flag,
            expedited_review_flag, advisory_committee,
            advisory_committee_description, regulation_number, device_class,
            medical_specialty, state, country_code
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """
    for batch in chunked(rows()):
        conn.executemany(sql, batch)
    conn.commit()

    loaded = conn.execute("SELECT COUNT(*) FROM nodes_raw").fetchone()[0]
    declared = record_source_meta(conn, "510k", metas)
    set_meta(conn, "raw_count.510k", raw_count)
    set_meta(conn, "loaded_count.510k", loaded)
    print(
        f"nodes_raw: declared {_fmt(declared)} | read {raw_count:,} | "
        f"loaded {loaded:,} ({raw_count - loaded:,} dupes)"
    )
    if unmapped:
        print(f"  WARNING unmapped 510k fields: {sorted(unmapped)}")

def load_recalls(conn: sqlite3.Connection) -> None:
    raw_count = 0
    metas: list[dict] = []

    def rows():
        nonlocal raw_count
        for record in iter_records("recall", metas):
            raw_count += 1
            # k_numbers is the curated per-recall list. openfda.k_number is the
            # firm's entire device catalogue and must never be used here.
            for k_number in record.get("k_numbers") or []:
                if not k_number:
                    continue
                yield (
                    record.get("cfres_id"),
                    k_number.strip().upper(),
                    record.get("product_res_number"),
                    record.get("res_event_number"),
                    iso_date(record.get("event_date_initiated")),
                    iso_date(record.get("event_date_posted")),
                    record.get("recall_status"),
                    record.get("recalling_firm"),
                    record.get("product_code"),
                    record.get("reason_for_recall"),
                    record.get("root_cause_description"),
                )

    sql = """
        INSERT OR IGNORE INTO recalls (
            cfres_id, k_number, product_res_number, res_event_number,
            event_date_initiated, event_date_posted, recall_status,
            recalling_firm, product_code, reason_for_recall,
            root_cause_description
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """
    for batch in chunked(rows()):
        conn.executemany(sql, batch)
    conn.commit()

    loaded = conn.execute("SELECT COUNT(*) FROM recalls").fetchone()[0]
    declared = record_source_meta(conn, "recall", metas)
    set_meta(conn, "raw_count.recall", raw_count)
    set_meta(conn, "loaded_count.recall", loaded)
    print(
        f"recalls: declared {_fmt(declared)} | read {raw_count:,} records -> "
        f"{loaded:,} (recall, k_number) pairs"
    )

def load_enforcement(conn: sqlite3.Connection) -> None:
    raw_count = 0
    metas: list[dict] = []

    def rows():
        nonlocal raw_count
        for record in iter_records("enforcement", metas):
            raw_count += 1
            yield (
                record.get("recall_number"),
                record.get("event_id"),
                record.get("classification"),
                record.get("status"),
                iso_date(record.get("recall_initiation_date")),
                iso_date(record.get("center_classification_date")),
                iso_date(record.get("report_date")),
                record.get("recalling_firm"),
            )

    sql = """
        INSERT OR IGNORE INTO enforcement (
            recall_number, event_id, classification, status,
            recall_initiation_date, center_classification_date,
            report_date, recalling_firm
        ) VALUES (?,?,?,?,?,?,?,?)
    """
    for batch in chunked(rows()):
        conn.executemany(sql, batch)
    conn.commit()

    loaded = conn.execute("SELECT COUNT(*) FROM enforcement").fetchone()[0]
    declared = record_source_meta(conn, "enforcement", metas)
    set_meta(conn, "raw_count.enforcement", raw_count)
    set_meta(conn, "loaded_count.enforcement", loaded)
    print(f"enforcement: declared {_fmt(declared)} | read {raw_count:,} | loaded {loaded:,}")


def load_registrations(conn: sqlite3.Connection) -> None:
    raw_count = 0
    metas: list[dict] = []

    def rows():
        nonlocal raw_count
        for record in iter_records("registrationlisting", metas):
            raw_count += 1
            k_number = (record.get("k_number") or "").strip().upper()
            if not k_number:
                continue  # PMA-track or exempt listings carry no K-number
            registration = record.get("registration") or {}
            yield (
                k_number,
                registration.get("registration_number"),
                registration.get("status_code"),
                registration.get("reg_expiry_date_year"),
                registration.get("name"),
                registration.get("iso_country_code"),
            )

    sql = """
        INSERT OR IGNORE INTO registrations (
            k_number, registration_number, status_code,
            reg_expiry_date_year, establishment_name, iso_country_code
        ) VALUES (?,?,?,?,?,?)
    """
    for batch in chunked(rows()):
        conn.executemany(sql, batch)
    conn.commit()

    loaded = conn.execute("SELECT COUNT(*) FROM registrations").fetchone()[0]
    declared = record_source_meta(conn, "registrationlisting", metas)
    set_meta(conn, "raw_count.registrationlisting", raw_count)
    set_meta(conn, "loaded_count.registrationlisting", loaded)
    print(
        f"registrations: declared {_fmt(declared)} | read {raw_count:,} -> "
        f"{loaded:,} (k_number, reg) pairs"
    )
    
def derive(conn: sqlite3.Connection) -> None:
    """Build the final nodes table from the loaded source tables.

    Pure derivation: nothing is mutated, so re-running is identical to
    running once, and every derived column's provenance is one query away.
    """
    conn.executescript(load_sql("derive"))
    conn.commit()
    print("derive: nodes built from nodes_raw + recalls + enforcement + registrations")

def build() -> None:
    NODES_DB.parent.mkdir(parents=True, exist_ok=True)
    if NODES_DB.exists():
        NODES_DB.unlink()  # processed/ is regenerable; always rebuild clean

    conn = sqlite3.connect(NODES_DB)
    # synchronous=OFF trades crash durability for speed. Safe precisely because
    # this file is regenerable from raw/ with one command.
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = OFF")
    conn.executescript(load_sql("schema"))

    load_nodes(conn)
    load_recalls(conn)
    load_enforcement(conn)
    load_registrations(conn)
    derive(conn)

    set_meta(conn, "built_at", datetime.now(timezone.utc).isoformat(timespec="seconds"))
    conn.commit()
    conn.close()