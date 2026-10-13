"""Write the published dataset from the pipeline's outputs.

Reads data/processed/nodes.db and data/processed/extractions/glm-high_corpus.jsonl
and writes dataset/:

  devices.csv              every 510(k) record, with recall and listing status
  links.csv                every predicate link: citing device -> predicate
  extractions.jsonl.gz     the model's raw output for each summary it read

Run from the repo root after the pipeline:  uv run python scripts/export_dataset.py
"""

import csv
import gzip
import shutil
import sqlite3

from predicate_graph.config import NODES_DB, OUT_DIR, PROJECT_ROOT

OUT = PROJECT_ROOT / "dataset"

DEVICE_COLUMNS = {
    "k_number": "k_number",
    "device_name": "device_name",
    "applicant": "applicant",
    "decision_date": "decision_date",
    "date_received": "date_received",
    "product_code": "product_code",
    "regulation_number": "regulation_number",
    "device_class": "device_class",
    "review_panel": "advisory_committee_description",
    "has_summary": "statement_or_summary = 'Summary'",
    "recalled": "recalled",
    "recall_class": "recall_class",
    "first_recall_date": "recall_date",
    "currently_listed": "actively_marketed",
}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    db = sqlite3.connect(NODES_DB)

    select = ", ".join(f"{expr} AS {name}" for name, expr in DEVICE_COLUMNS.items())
    rows = db.execute(f"SELECT {select} FROM nodes ORDER BY k_number")
    with open(OUT / "devices.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(DEVICE_COLUMNS)
        writer.writerows(
            [r[0], *r[1:9], int(r[9] or 0), int(r[10] or 0), r[11] or "", r[12] or "", int(r[13] or 0)] for r in rows
        )

    # One row per (citing, predicate). A K-number citation wins over a name
    # match for the same pair; name matches carry their match score.
    links = {}
    for c, p, page, quote in db.execute("SELECT citing, predicate, page, quote FROM edges WHERE valid = 1"):
        links[(c, p)] = ("k_number", "", page, quote)
    for c, p, score, page, quote in db.execute("SELECT citing, predicate, score, page, quote FROM edges_name_only"):
        links.setdefault((c, p), ("name", round(score, 1), page, quote))
    with open(OUT / "links.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["citing", "predicate", "matched_by", "name_score", "page", "quote"])
        for (c, p), (by, score, page, quote) in sorted(links.items()):
            writer.writerow([c, p, by, score, page or "", (quote or "").strip()])

    with open(OUT_DIR / "glm-high_corpus.jsonl", "rb") as src, gzip.open(OUT / "extractions.jsonl.gz", "wb") as dst:
        shutil.copyfileobj(src, dst)

    print(f"devices: {db.execute('SELECT COUNT(*) FROM nodes').fetchone()[0]:,}, links: {len(links):,} -> {OUT}")


if __name__ == "__main__":
    main()
