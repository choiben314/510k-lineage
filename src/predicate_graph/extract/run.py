"""Call Claude to extract predicates from 510(k) documents.

Results are cached to JSONL, one file per model, one line per K-number --
same pattern as the raw-data manifest. Reruns skip whatever's already there,
so a partial run (crash, rate limit, Ctrl-C) costs nothing to resume.
"""

import json
import csv
import os
from pathlib import Path
from datetime import datetime
from collections import Counter
import httpx

import instructor
from anthropic import Anthropic
from openai import OpenAI, DefaultHttpxClient
from pyrate_limiter import Duration, Limiter, Rate

from predicate_graph.config import LABELS, OUT_DIR, RUNS_DIR, TXT_DIR
from predicate_graph.extract.prompt import EXTRACTION_PROMPT
from predicate_graph.extract.schema import Extraction
from predicate_graph.ingest.documents import UA, get_text
from predicate_graph.parallel import parallel

from concurrent.futures.process import BrokenProcessPool

MODELS = {
    "haiku":  ("anthropic", "claude-haiku-4-5", {}),
    "sonnet": ("anthropic", "claude-sonnet-5", {}),
    "opus":   ("anthropic", "claude-opus-5", {}),
    # "glm": ("glm", "glm-5.3-flash", {}),
    # "glm-high": ("baseten", "zai-org/GLM-5.3-Flash", {"reasoning_effort": "high"}),
    # "glm-high": ("fireworks", "accounts/fireworks/models/glm-5p3-flash", {"reasoning_effort": "high"}),
    "glm-high-zai": ("glm", "glm-5.3-flash", {"reasoning_effort": "high"}),
    "glm-high": ("together", "zai-org/GLM-5.3-Flash", {"reasoning_effort": "high"}),
    "openai": ("openai", "gpt-5.6-luna", {"reasoning_effort": "xhigh"})
}

TOGETHER_LIMITER = Limiter(Rate(10, Duration.SECOND))
ZAI_LIMITER = Limiter(Rate(3, Duration.SECOND * 5))
FDA_LIMITER = Limiter(Rate(2, Duration.SECOND))

_CLIENTS = {}
def _client(provider: str):
    if provider not in _CLIENTS:
        if provider == "anthropic":
            _CLIENTS[provider] = instructor.from_anthropic(Anthropic())
        elif provider == "openai":
            # TOOLS mode (instructor's default) uses function calling, which
            # OpenAI rejects alongside reasoning_effort on this model/endpoint.
            _CLIENTS[provider] = instructor.from_openai(OpenAI(max_retries=7), mode=instructor.Mode.JSON)
        elif provider == "glm":
            _CLIENTS[provider] = instructor.from_openai(
                OpenAI(
                    api_key=os.environ["GLM_API_KEY"], 
                    base_url="https://api.z.ai/api/paas/v4", 
                    max_retries=7,
                    http_client=DefaultHttpxClient(
                        event_hooks={"request": [lambda request: ZAI_LIMITER.try_acquire("zai")]}
                    )
                ),
                mode=instructor.Mode.JSON,
            )
        elif provider == "together":
            _CLIENTS[provider] = instructor.from_openai(
                OpenAI(
                    api_key=os.environ["TOGETHER_API_KEY"],
                    base_url="https://api.together.xyz/v1",
                    max_retries=7,
                    http_client=DefaultHttpxClient(
                        event_hooks={"request": [lambda request: TOGETHER_LIMITER.try_acquire("together")]}
                    ),
                ),
                mode=instructor.Mode.JSON,
            )
        else:
            raise ValueError(f"unknown provider {provider!r}")
    return _CLIENTS[provider]

_SPLIT_MARKER = "Document (K-number"
_STABLE, _TAIL_TEMPLATE = EXTRACTION_PROMPT.split(_SPLIT_MARKER, 1)
_TAIL_TEMPLATE = _SPLIT_MARKER + _TAIL_TEMPLATE


def extract_one(provider: str, model_id: str, k_number: str, text: str, extra: dict) -> Extraction | None:
    """One extraction call. Returns None (and prints why) on any failure --
    a bad document should never take down the rest of the run."""

    client = _client(provider)
    tail = _TAIL_TEMPLATE.format(k_number=k_number, document_text=text)

    try:
        if provider == "anthropic":
            return client.chat.completions.create(
                model=model_id,
                max_tokens=16000,
                system=[{"type": "text", "text": _STABLE, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": tail}],
                response_model=Extraction,
                max_retries=3,
                **extra,
            )
        elif provider == "openai":
            return client.chat.completions.create(
                model=model_id,
                max_completion_tokens=16000,
                messages=[
                    {"role": "system", "content": _STABLE},
                    {"role": "user", "content": tail},
                ],
                response_model=Extraction,
                max_retries=3,
                **extra,
            )
        elif provider in ("glm", "together"):
            return client.chat.completions.create(
                model=model_id,
                max_tokens=16000,
                messages=[
                    {"role": "system", "content": _STABLE},
                    {"role": "user", "content": tail},
                ],
                response_model=Extraction,
                max_retries=3,
                **extra,
            )
    except Exception as e:
        print(f"  {k_number} FAILED: {e}")
        return None

def load_cached(out_path: Path) -> dict[str, Extraction]:
    if not out_path.exists():
        return {}
    cached = {}
    with out_path.open() as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cached[data["k_number"]] = Extraction.model_validate(data)
    return cached

def extract_k_numbers(model_key: str, k_numbers: list[str], out_path: Path | None = None, workers: int = 8) -> dict[str, Extraction]:
    """Run extraction over the eval sample for one model, resumable."""
    provider, model_id, extra = MODELS[model_key]
    out_path = out_path or (OUT_DIR / f"{model_key}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    cached = load_cached(out_path)
    requested = set(k_numbers)
    results = dict(cached)

    k_todos = [k for k in k_numbers if k not in cached and not (TXT_DIR / f"{k}.missing").exists()]
    counts = Counter()
    counts['already cached'] = len(k_numbers) - len(k_todos)
    _client(provider)

    with httpx.Client(
        timeout=30.0, 
        headers={"User-Agent": UA},
        event_hooks={"request": [lambda request: FDA_LIMITER.try_acquire("fda")]}
    ) as http:

        def get_text_or_none(k):
            try:
                return get_text(http, k)
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (403, 429):
                    raise
                print(f" {k} read failed: {e}")
            except BrokenProcessPool:
                raise
            except Exception as e:
                print(f" {k} read failed: {e}")
            return None
        
        def work(k):
            fetched = get_text_or_none(k)
            if fetched is None:
                return k, "fetch failed", None
            _, text, status = fetched
            if status == "missing pdf":
                return k, "no summary", None

            result = extract_one(provider, model_id, k, text, extra)
            return k, "extracted" if result else "extraction failed", result
        
        with out_path.open("a") as out:
            for i, (k, status, result) in enumerate(parallel(work, k_todos, workers), 1):
                counts[status] += 1
                if result is None:
                    print(f"[{i}/{len(k_todos)}] {k} {status}")
                    continue
                out.write(result.model_dump_json() + "\n")
                out.flush()
                results[k] = result
                print(f"[{i}/{len(k_todos)}] {k} extracted "
                    f"({len(result.predicates)} predicates, "
                    f"{len(result.predicates_name_only)} name-only)")

    print(f"\n{model_key}: {dict(counts)}"
          f" Wrote {out_path}")

    return {k: v for k, v in results.items() if k in requested}

def record_run(model_key: str, filters: dict, k_numbers: list[str]) -> Path:
    ts = datetime.now().strftime("%Y-%m-%dT%H%M%S")
    path = RUNS_DIR / f"{model_key}_{ts}.json"
    path.write_text(json.dumps({
        "model": model_key,
        "filters": filters,
        "requested": k_numbers
    }))
    return path

def requested_k_numbers(model_key: str) -> set[str]:
    requested = set()
    for path in RUNS_DIR.glob(f"{model_key}_*.json"):
        requested.update(json.loads(path.read_text())['requested'])
    return requested

def corpus_path(model_key: str) -> Path:
    return OUT_DIR / f"{model_key}_corpus.jsonl"

def run_eval_extraction(model_key: str, head: int) -> None:
    with open(LABELS / "eval_sample.csv") as f:
        k_numbers = [r["k_number"] for r in csv.DictReader(f)][:head]
    extract_k_numbers(model_key, k_numbers)

