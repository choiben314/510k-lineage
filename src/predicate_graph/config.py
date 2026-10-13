from pathlib import Path
from importlib.resources import files

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA = PROJECT_ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
PROCESSED = DATA / "processed"

LABELS = PROJECT_ROOT / "labels"

MANIFEST = RAW / "manifest.jsonl"
NODES_DB = PROCESSED / "nodes.db"
OUT_DIR = PROCESSED / "extractions"
PDF_DIR = RAW / "pdfs"
TXT_DIR = INTERIM / "txt"

RUNS_DIR = OUT_DIR / "runs"

_DIRS = (RAW, INTERIM, PROCESSED, LABELS, OUT_DIR, PDF_DIR, TXT_DIR, RUNS_DIR)

def ensure_dirs() -> None:
    for dir in _DIRS:
        dir.mkdir(parents=True, exist_ok=True)

def load_sql(name: str) -> str:
    """Read a .sql file that ships inside the package"""
    return (files("predicate_graph") / "sql" / f"{name}.sql").read_text(encoding="utf-8")