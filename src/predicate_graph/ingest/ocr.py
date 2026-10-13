import subprocess
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import objc
import Vision
from Foundation import NSURL

POOL = ProcessPoolExecutor(max_workers=6)

def _recognize_image(image_path: Path) -> str:
    """OCR one page image with Apple's Vision framework."""
    with objc.autorelease_pool():
        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(["en-US"])
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(
            NSURL.fileURLWithPath_(str(image_path)), None
        )
        handler.performRequests_error_([request], None)
        return "\n".join(obs.topCandidates_(1)[0].string() for obs in (request.results() or []))

def recognize_pdf(pdf_path: Path, max_pages: int) -> list[str]:
    """Use Apple Vision framework to maximize local compute efficiency"""
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["mutool", "draw", "-c", "gray", "-o", f"{tmp}/p_%d.png", "-r", "150", str(pdf_path), f"1-{max_pages}"],
            capture_output=True,
        )
        pages = sorted(Path(tmp).glob(f"p_*.png"), key=lambda p: int(p.stem.split("_")[1]))
        return [_recognize_image(page) for page in pages]