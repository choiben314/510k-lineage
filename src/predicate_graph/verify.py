from __future__ import annotations

import sqlite3

from predicate_graph.config import NODES_DB

ENDPOINTS = ("510k", "recall", "enforcement", "registrationlisting")


def _scalar(conn: sqlite3.Connection, sql: str, *args):
    return conn.execute(sql, args).fetchone()[0]


def verify() -> None:
    if not NODES_DB.exists():
        raise SystemExit("no nodes.db -- run `pg build-nodes` first")

    conn = sqlite3.connect(NODES_DB)
    m = dict(conn.execute("SELECT key, value FROM meta"))
    total = _scalar(conn, "SELECT COUNT(*) FROM nodes")

    # ---------------------------------------------------------------- integrity
    print("=" * 66)
    print("INTEGRITY".center(66))
    print("=" * 66)
    bad = []
    for endpoint in ENDPOINTS:
        declared, read = m.get(f"declared_total.{endpoint}"), m.get(f"raw_count.{endpoint}")
        if declared != read:
            bad.append(endpoint)
        print(
            f"  {endpoint:20s} {declared:>8} records declared, {read:>8} read, "
            f"as of {m.get(f'last_updated.{endpoint}')}"
        )
    nodes_raw = _scalar(conn, "SELECT COUNT(*) FROM nodes_raw")
    print(f"\n  nodes_raw {nodes_raw:,} -> nodes {total:,}")
    if bad or nodes_raw != total:
        print(f"  FAIL: {bad or 'derive changed row count'}")
    else:
        print("  -> every record accounted for; derive dropped and duplicated nothing")

    # ------------------------------------------------------------------- corpus
    lo = _scalar(conn, "SELECT MIN(decision_date) FROM nodes")
    hi = _scalar(conn, "SELECT MAX(decision_date) FROM nodes")
    print(f"\n  {total:,} clearances, {lo} to {hi}")

    # ------------------------------------------------- extractable universe
    print("\n" + "=" * 66)
    print("EXTRACTABLE UNIVERSE".center(66))
    print("=" * 66)
    print(f"  {'decade':8s}{'summary':>10s}{'statement':>11s}{'blank':>9s}{'total':>9s}")
    for row in conn.execute(
        """
        SELECT substr(decision_date,1,3)||'0s',
               SUM(statement_or_summary='Summary'),
               SUM(statement_or_summary='Statement'),
               SUM(statement_or_summary=''),
               COUNT(*)
        FROM nodes GROUP BY 1 ORDER BY 1
        """
    ):
        print(f"  {row[0]:8s}{row[1]:>10,}{row[2]:>11,}{row[3]:>9,}{row[4]:>9,}")

    summaries = _scalar(conn, "SELECT COUNT(*) FROM nodes WHERE statement_or_summary='Summary'")
    print(f"\n  -> {summaries:,} extractable summaries ({summaries/total:.0%} of corpus)")
    print("  -> the rest is structurally dark: statements disclose nothing by")
    print("     design, and blanks are almost entirely pre-1990 with no PDF online")

    # -------------------------------------------------------- recall exposure
    print("\n" + "=" * 66)
    print("RECALL EXPOSURE".center(66))
    print("=" * 66)
    recalled = _scalar(conn, "SELECT COUNT(*) FROM nodes WHERE recalled=1")
    print(f"  {recalled:,} devices with >=1 recall ({recalled/total:.1%})")
    for value, count in conn.execute(
        "SELECT recall_class, COUNT(*) FROM nodes WHERE recalled=1 "
        "GROUP BY 1 ORDER BY 2 DESC"
    ):
        print(f"    {value or 'unclassified':14s} {count:>7,}")

    class1_live = _scalar(
        conn,
        "SELECT COUNT(*) FROM nodes WHERE recall_class='Class I' AND actively_marketed=1",
    )
    print(f"\n  -> {class1_live:,} Class I recalled devices are still actively listed")
    print("  -> Class I = reasonable probability of serious injury or death")
    print("  -> this is the direct count; descendants will make it larger")

    # -------------------------------------------------------- marketing status
    print("\n" + "=" * 66)
    print("MARKETING STATUS".center(66))
    print("=" * 66)
    live = _scalar(conn, "SELECT COUNT(*) FROM nodes WHERE actively_marketed=1")
    dead = _scalar(conn, "SELECT COUNT(*) FROM nodes WHERE actively_marketed=0")
    unknown = _scalar(conn, "SELECT COUNT(*) FROM nodes WHERE actively_marketed IS NULL")
    print(f"  listed & active  {live:>8,} ({live/total:.1%})")
    print(f"  listed, inactive {dead:>8,} ({dead/total:.1%})")
    print(f"  not listed       {unknown:>8,} ({unknown/total:.1%})")
    print("\n  -> 'inactive' is negligible, so the real split is listed vs not")
    print(f"  -> use {live:,} as the denominator for 'currently marketed' claims;")
    print("     absence from Registration & Listing is evidence, not proof")

    # ------------------------------------------------------- cohort readiness
    print("\n" + "=" * 66)
    print("MESH COHORT (Day 2 labelling, Day 10 scale target)".center(66))
    print("=" * 66)
    for row in conn.execute(
        """
        SELECT product_code, COUNT(*), SUM(statement_or_summary='Summary'), SUM(recalled)
        FROM nodes WHERE product_code IN ('FTL','OTN','FTM','OWA')
        GROUP BY 1 ORDER BY 2 DESC
        """
    ):
        print(f"  {row[0]:6s} {row[1]:>5,} devices  {row[2]:>5,} summaries  {row[3]:>4,} recalled")
    cohort = _scalar(
        conn,
        "SELECT COUNT(*) FROM nodes WHERE product_code IN ('FTL','OTN','FTM','OWA') "
        "AND statement_or_summary='Summary'",
    )
    print(f"\n  -> {cohort:,} documents to fetch and extract for the mesh cohort")

    conn.close()