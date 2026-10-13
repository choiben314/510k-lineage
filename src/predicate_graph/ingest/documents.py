"""Fetch 510(k) PDFs by K-number and extract their text; try embedded PDF first with OCR fallback
"""

import re
import subprocess
from pathlib import Path

import httpx

from predicate_graph.config import PDF_DIR, TXT_DIR
from predicate_graph.ingest import ocr

UA = "predicate-graph/0.1"
BASE = "https://www.accessdata.fda.gov/cdrh_docs"
MAX_PAGES = 10

# pdf/ holds everything through 2001; pdf2..pdf9 are 2002-2009; pdf10+ after.
def archive_dir(k_number: str) -> str:
    year = int(k_number[1:3])
    if year <= 1 or year >= 96:
        return "pdf"
    return f"pdf{year}"


def fetch_pdf(client: httpx.Client, k_number: str) -> Path | None:
    dest = PDF_DIR / f"{k_number}.pdf"
    if dest.exists():
        return dest
    url = f"{BASE}/{archive_dir(k_number)}/{k_number}.pdf"
    response = client.get(url, follow_redirects=True)
    # No summary
    if response.status_code == 404:
        return None
    response.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(response.content)
    return dest

def _mark_pages(pages: list[str]) -> str:
    """Stamp pages for model provenance extraction. Capped at MAX_PAGES."""
    return "\n\n".join(
        f"[Page {i}]\n{page.strip()}" for i, page in enumerate(pages[:MAX_PAGES], 1) if page.strip()
    )

def is_scanned(pdf_path: Path) -> bool:
    listing = subprocess.run(
        ["pdfimages", "-list", "-f", "1", "-l", "1", str(pdf_path)],
        capture_output=True, text=True,
    ).stdout.splitlines()[2:]
    return any(int(row.split()[3]) >= 1000 and int(row.split()[4]) >= 1000 for row in listing)

def _fix_k_numbers(text: str) -> str:
    """Replace letter 'O' with zero"""
    return re.sub(r"\bK[O\d]{6}\b", lambda m: m.group().replace("O", "0"), text)

def _cites_other_k_numbers(text: str, own: str) -> bool:
    return bool({m.upper() for m in re.compile(r"\b[Kk]\d{6}\b").findall(text)} - {own})

def pdf_to_text(pdf_path: Path) -> str:
    if not is_scanned(pdf_path):
        result = subprocess.run(
            ["pdftotext", "-l", str(MAX_PAGES), "-layout", str(pdf_path), "-"],
            capture_output=True, text=True,
        )
        text = result.stdout.strip()
        pages = text.split("\x0c")
        if len(text) > 200 and _cites_other_k_numbers(text, pdf_path.stem):
            return _mark_pages(pages)
    pages = ocr.POOL.submit(ocr.recognize_pdf, pdf_path, MAX_PAGES).result()
    return _fix_k_numbers(_mark_pages(pages))

def get_text(client: httpx.Client, k: str) -> tuple[str, str, str]:
    txt_path = TXT_DIR / f"{k}.txt"
    missing_path = TXT_DIR / f"{k}.missing"
    if txt_path.exists():
        return k, txt_path.read_text(), "cached"
    if missing_path.exists():
        return k, "", "missing pdf"
    
    pdf_path = fetch_pdf(client, k)
    if pdf_path is None:
        missing_path.touch()
        return k, "", "missing pdf"
    text = pdf_to_text(pdf_path)
    txt_path.write_text(text)
    return k, text, f"{len(text)} chars"