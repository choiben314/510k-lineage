"""Enabling fuzzy-matching of predicates identified by name-only"""

import sqlite3
from dataclasses import dataclass

from rapidfuzz import fuzz, process, utils

from predicate_graph.config import NODES_DB, TXT_DIR
from predicate_graph.extract.schema import Extraction
from functools import cache

from enum import Enum

from collections import defaultdict

import re

NAME_MATCH_FLOOR = 80
WIN_MARGIN = 5
_PRE_AMENDMENT = re.compile(r"pre-?\s?amendment|pre-?1976|prior to may 28,? 1976", re.I)
_ENGLISH = {w.strip().lower() for w in open("/usr/share/dict/words")}

class MatchStatus(str, Enum):
    NO_SUMMARY="No Summary"
    NO_NAMES="No Names to Resolve"
    NO_MATCH="No Match Found"
    RESOLVED_BY_K="Resolved By K Number"
    RESOLVED_BY_NAME="Resolved By Name"
    EXTRACTION_FAILED="Extraction Failed"

@dataclass
class NameResolution:
    citing: str
    name: str
    resolved_k_number: str | None
    score: float
    page: int
    quote: str
    citing_date: str | None
    predicate_date: str | None

    @property
    def resolved(self) -> bool:
        return self.resolved_k_number is not None

@cache
def _brand_words(s: str) -> frozenset[str]:
    def english(w):
        return w in _ENGLISH or any(w.endswith(x) and w[:-len(x)] in _ENGLISH for x in ("s", "es", "ed", "d", "ing", "ly", "er"))
    return frozenset(w for w in utils.default_process(s).split() if w.isalpha() and len(w) >= 3 and not english(w))

@cache
def _numbered_words(s: str) -> set[str]:
    """Returns words containing a digit (e.g. '100S Sterilization' -> {'100s'})"""
    return {word for word in utils.default_process(s).split() if any(ch.isdigit() for ch in word)}

def _best_match(name: str, allowed_applicants: frozenset[str] | None, citing: str, before_date: str | None, nodes: list[tuple[str, str, str]]) -> tuple[str | None, float]:

    numbers = _numbered_words(name)
    brand = _brand_words(name)

    if allowed_applicants is None and not brand and not numbers:
        return None, 0.0

    candidates, branded = {}, {}
    for node_k, node_name, node_applicant, node_date  in nodes:
        # empirical, high confidence filters
        if node_k == citing:
            continue

        if not (node_name and node_date and before_date and node_date <= before_date):
            continue

        if allowed_applicants is not None and node_applicant not in allowed_applicants:
            continue

        if not numbers <= _numbered_words(node_name):
            continue
        candidates[node_k] = node_name
        if brand and brand <= set(utils.default_process(f"{node_name} {node_applicant or ''}").split()):
            branded[node_k] = node_name

    if brand:
        if branded:
            candidates = branded
        elif allowed_applicants is None:
            return None, 0.0

    top = process.extract(
        name,
        candidates,
        scorer=fuzz.token_sort_ratio, 
        processor=utils.default_process,
        limit=2
    )

    best_k, best_score = None, 0.0
    if not top:
        return best_k, best_score

    best_name, best_score, best_k = top[0]
    if best_score < NAME_MATCH_FLOOR:
        return None, best_score
    if len(top) == 2:
        _, runner_up_score, _ = top[1]
        if best_score - runner_up_score < WIN_MARGIN:
            return None, best_score
    return best_k, best_score

def resolve_extractions(extractions: list[Extraction]) -> list[NameResolution]:
    conn = sqlite3.connect(NODES_DB)
    nodes = conn.execute("SELECT k_number, device_name, applicant, decision_date FROM nodes").fetchall()
    dates = {k: date for k, _, _, date in nodes}
    conn.close()

    all_applicants = sorted({a for _, _, a, _ in nodes if a})

    @cache
    def matching_applicants(applicant: str) -> frozenset[str]:
        hits = process.extract(applicant, all_applicants, scorer=fuzz.partial_ratio,
                               processor=utils.default_process, score_cutoff=NAME_MATCH_FLOOR, limit=None)
        return frozenset(a for a, _, _ in hits)

    results = []
    for e in extractions:
        citing_date = dates.get(e.k_number)
        for np in e.predicates_name_only:
            if _PRE_AMENDMENT.search(f"{np.name} {np.quote}"):
                k_number, score = None, 0.0
            else:
                allowed_applicants = matching_applicants(np.applicant) if np.applicant else None
                k_number, score = _best_match(np.name, allowed_applicants, e.k_number, citing_date, nodes)
            resolved_k_number = k_number if score >= NAME_MATCH_FLOOR else None
            results.append(
                NameResolution(
                    citing=e.k_number,
                    name=np.name,
                    resolved_k_number=resolved_k_number,
                    score=score,
                    page=np.page,
                    quote=np.quote,
                    citing_date=citing_date,
                    predicate_date=dates.get(resolved_k_number) if resolved_k_number else None
                )
            )

    return results

def summarize(results: list[NameResolution], extractions: dict[str, Extraction], requested: set[str]) -> None:
    resolved = [r for r in results if r.resolved]
    resolved_citing = {r.citing for r in resolved}

    print(f"\n===Name Resolution===\n\
          {len(results)} name-only citations, {len(resolved)} resolved (score >= {NAME_MATCH_FLOOR}),\n\
          {len(results) - len(resolved)} left unknown")

    statuses: dict[MatchStatus, int] = defaultdict(int)
    for requested_k in sorted(requested):
        e = extractions.get(requested_k)
        if e is None:
            has_summary = (TXT_DIR / f"{requested_k}.txt").exists()
            statuses[MatchStatus.EXTRACTION_FAILED if has_summary else MatchStatus.NO_SUMMARY] += 1
        elif e.predicates:
            statuses[MatchStatus.RESOLVED_BY_K] += 1
        elif requested_k in resolved_citing:
            statuses[MatchStatus.RESOLVED_BY_NAME] += 1
        elif e.predicates_name_only:
            statuses[MatchStatus.NO_MATCH] += 1
        else:
            statuses[MatchStatus.NO_NAMES] += 1

    for status in MatchStatus:
        print(f"# {status.value}: {statuses.get(status, 0)}")