import typer
import csv
import httpx

from predicate_graph.config import ensure_dirs, LABELS
from predicate_graph.ingest.download import ENDPOINTS, sync
from predicate_graph.ingest.peek import peek as peek_endpoint
from predicate_graph.ingest.nodes import build as build_nodes_impl
from predicate_graph.ingest.documents import get_text
from predicate_graph.verify import verify as verify_impl
from predicate_graph.evals.sample import build_sample as build_sample_impl
from predicate_graph.evals.sample import top_up as top_up_impl
from predicate_graph.evals.score import score_model as score_model_impl
from predicate_graph.extract.select import select_targets
from predicate_graph.extract.run import run_eval_extraction, load_cached, MODELS, OUT_DIR, record_run, requested_k_numbers, corpus_path, extract_k_numbers
from predicate_graph.graph.validate import validate_extractions, summarize
from predicate_graph.graph.trace import trace as trace_impl
from predicate_graph.graph.edges import build_edges as build_edges_impl, build_edges_name_only as build_edges_name_only_impl
from predicate_graph.parallel import parallel

app = typer.Typer(help="Predicate graph pipeline for FDA 510(k) clearances.")

@app.callback()
def main_callback():
    """Runs before any subcommand"""
    ensure_dirs()

@app.command()
def download(endpoint: str="all") -> None:
    """Sync openFDA bulk partitions into data/raw/"""
    targets = ENDPOINTS if endpoint == "all" else (endpoint,)
    sync(targets)

@app.command()
def peek(endpoint: str, n: int=1) -> None:
    """Print the first n raw records of an endpoint."""
    peek_endpoint(endpoint, n)

@app.command()
def build_nodes() -> None:
    """Rebuild nodes.db from data/raw/"""
    build_nodes_impl()

@app.command()
def verify() -> None:
    """Print row counts, ranges, and join rates"""
    verify_impl()

@app.command()
def build_sample() -> None:
    """Draw the reproducible stratified eval sample."""
    build_sample_impl()

def main():
    app()

@app.command()
def fetch_eval_docs(max_rounds: int = 5) -> None:
    """Fetch + extract text for the eval sample's 50 documents.

    Some fetches fail transiently or hit a genuine 404. After each round,
    any row still missing text gets replaced with a same-stratum draw
    (evals.sample.top_up) and re-fetched, up to max_rounds times.
    """
    for round_n in range(1, max_rounds + 1):
        with open(LABELS / "eval_sample.csv") as f:
            k_numbers = [r["k_number"] for r in csv.DictReader(f)]
        with httpx.Client(timeout=30.0, headers={"User-Agent": UA}) as http:
            results = list(parallel(lambda k: get_text(http, k), k_numbers, 8))
        missing = [k for k, _, status in results if status == "missing pdf"]

        if not missing:
            return

        if round_n == max_rounds:
            break

        print(f"\nround {round_n}: {len(missing)} missing, topping up and retrying")
        top_up_impl(round_n)

    print(f"\ngave up after {max_rounds} rounds -- check labels/eval_sample.csv by hand")

@app.command()
def extract_eval(model: str, head: int=50) -> None:
    """Run extraction over the eval sample. model: haiku | sonnet | opus | openai | glm."""
    if model not in MODELS:
        raise SystemExit(f"model must be one of {list(MODELS)}, got {model!r}")
    run_eval_extraction(model, head)

@app.command()
def extract_set(model: str, since: str | None = typer.Option(None, help="(YYYY-MM-DD)"), until: str | None = typer.Option(None, help="(YYYY-MM-DD)"), limit: int | None = None, workers: int = 8):
    if model not in MODELS:
        raise SystemExit(f"model must be one of {list(MODELS)}, got {model!r}")
    k_numbers_to_extract = select_targets(since, until, limit)
    filters = {
        "since": since,
        "until": until,
        "limit": limit
    }
    record = record_run(model, filters, k_numbers_to_extract)
    print(f"{len(k_numbers_to_extract)} documents requested (run recorded in {record.name})")
    extract_k_numbers(model, k_numbers_to_extract, corpus_path(model), workers=workers)

@app.command()
def score(model: str) -> None:
    """Score extractions against golden dataset"""
    score_model_impl(model)

@app.command()
def validate(model: str) -> None:
    """Run simple, deterministic validation on extracted edges"""
    extractions = list(load_cached(OUT_DIR / f"{model}.jsonl").values())
    results = validate_extractions(extractions)
    summarize(results)

@app.command()
def trace(model: str, seeds: list[str]) -> None:
    """Run fan-out extraction from seed"""
    trace_impl(model, seeds, OUT_DIR / f"{model}_trace.jsonl")

@app.command()
def build_edges(model: str) -> None:
    """Build edges DB for visualization"""
    build_edges_impl(corpus_path(model))

@app.command()
def resolve_names(model: str, eval: bool = False) -> None:
    """Resolve name-only extractions with fuzzy matching"""
    if eval:
        path = OUT_DIR / f"{model}.jsonl"
        with open(LABELS / "eval_sample.csv") as f:
            requested = {row["k_number"] for row in csv.DictReader(f)}
    else:
        path = corpus_path(model)
        requested = requested_k_numbers(model)
    build_edges_name_only_impl(path, requested)