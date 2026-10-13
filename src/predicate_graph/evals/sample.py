"""Draw a reproducible stratified sample of documents for the eval set."""

import csv
import random
import sqlite3

from predicate_graph.config import LABELS, NODES_DB

SEED = 42
N_SUMMARY = 45
N_NEGATIVE = 5

COLUMNS = [
    "read", "k_number", "decision_date", "decade", "doc_type", "product_code",
    "device_name", "applicant", "predicates", "predicates_name_only",
    "reference_devices", "notes",
]

QUERY = """
    SELECT k_number, decision_date, device_name, applicant, product_code,
           substr(decision_date, 1, 3) || '0s' AS decade
    FROM nodes
    WHERE statement_or_summary = ? AND decision_date >= '1996-01-01'
"""


def allocate(sizes, n):
    """Split n slots across strata in proportion to their size.

    Floor each share, then give leftover slots to the largest remainders,
    so the result always sums to exactly n.
    """
    total = sum(sizes.values())
    exact = {k: v / total * n for k, v in sizes.items()}
    slots = {k: int(v) for k, v in exact.items()}
    leftover = n - sum(slots.values())
    ranked = sorted(exact, key=lambda k: exact[k] - int(exact[k]), reverse=True)
    for k in ranked[:leftover]:
        slots[k] += 1
    return slots


def build_sample():
    conn = sqlite3.connect(NODES_DB)
    conn.row_factory = sqlite3.Row
    rng = random.Random(SEED)

    summaries = conn.execute(QUERY, ("Summary",)).fetchall()
    statements = conn.execute(QUERY, ("Statement",)).fetchall()

    by_decade = {}
    for row in summaries:
        by_decade.setdefault(row["decade"], []).append(row)
    sizes = {decade: len(rows) for decade, rows in by_decade.items()}
    slots = allocate(sizes, N_SUMMARY)

    sample = []
    for decade in sorted(by_decade):
        picked = rng.sample(by_decade[decade], slots[decade])
        sample += [(row, "Summary") for row in picked]
        print(f"{decade}  {sizes[decade]:>6,} available  {slots[decade]:>2} sampled")

    sample += [(row, "Statement") for row in rng.sample(statements, N_NEGATIVE)]
    print(f"negatives  {len(statements):>6,} available  {N_NEGATIVE:>2} sampled")

    out = LABELS / "eval_sample.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row, doc_type in sample:
            blank = {column: "" for column in COLUMNS}
            writer.writerow({**blank, **dict(row), "doc_type": doc_type})

    conn.close()
    print(f"\nwrote {out} ({len(sample)} documents)")


def top_up(round_n: int = 1):
    """Replace any eval_sample.csv row with no fetched text.

    Draws a replacement from the SAME stratum (decade + doc_type) as the
    row being replaced, excluding every K-number already in the sample.
    Seeded on SEED + round_n: each retry round gets a genuinely different
    seed (so two documents can't just swap back and forth forever), but a
    given round_n always reproduces the same pick -- fully deterministic.
    """
    import csv as csv_mod
    from predicate_graph.config import RAW

    path = LABELS / "eval_sample.csv"
    rows = list(csv_mod.DictReader(open(path)))
    have_txt = {p.stem for p in (RAW.parent / "interim" / "txt").glob("*.txt")}
    already = {r["k_number"] for r in rows}

    conn = sqlite3.connect(NODES_DB)
    conn.row_factory = sqlite3.Row
    rng = random.Random(SEED + round_n)

    n_replaced = 0
    for row in rows:
        if row["k_number"] in have_txt:
            continue
        candidates = conn.execute(
            QUERY + " AND decade = ?",
            (row["doc_type"], row["decade"]),
        ).fetchall()
        candidates = [c for c in candidates if c["k_number"] not in already]
        pick = rng.choice(candidates)
        already.add(pick["k_number"])
        old_k = row["k_number"]
        row.update({k: pick[k] for k in ("k_number", "decision_date", "device_name",
                                          "applicant", "product_code")})
        print(f"replaced {old_k} -> {row['k_number']} ({row['decade']}, {row['doc_type']})")
        n_replaced += 1

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv_mod.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    conn.close()
    print(f"\n{n_replaced} rows replaced, wrote {path}")
