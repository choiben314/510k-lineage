# 510(k) Lineage

Most medical devices in the U.S. are cleared through the FDA's 510(k) process by showing they are substantially equivalent to a device already on the market, called a predicate. The FDA's database records every clearance but not the predicate; that is written only in the summary PDF each company files.

This repository contains a dataset of those predicate links, extracted from every 510(k) summary the FDA hosts, and the code that produced it.

## Dataset

In [`dataset/`](dataset/):

| File | Rows | What it is |
|---|---|---|
| `links.csv` | 141,040 | One row per link from a device to a predicate its summary names: `citing`, `predicate`, `matched_by`, `name_score`, `page`, `quote` |
| `devices.csv` | 175,757 | Every 510(k) record from openFDA, with product code, review panel, recall status and whether the device is currently listed |
| `extractions.jsonl.gz` | 80,886 | The model's raw output for each of 80,869 summaries: predicates cited by K-number, predicates cited only by name, reference devices, and the page and quote for each. A few summaries were re-read and appear twice; the last line is the one used |

`matched_by` is `k_number` when the summary cites the predicate's K-number (137,887 links), or `name` when it names the predicate without one and the name was matched to a device in the FDA database (3,153 links).

Each link's `page` and `quote` point to the sentence in the citing device's summary, at `https://www.accessdata.fda.gov/cdrh_docs/pdf{YY}/{K-number}.pdf`. For K-numbers from 1996–2001 the folder is `pdf` with no year.

Device and recall records are as of August 2026.

## Accuracy

- **K-number links:** 150 of 150 correct in a random sample checked by hand against the PDFs (95% interval 97.5–100%).
- **Name-matched links:** 46 of 50 correct (81–97%). The remaining errors are mostly one version of a product mistaken for another.
- **Recall:** on a 50-document hand-labeled set (`labels/gold.jsonl`), 98.7% of predicates were found.
- **Coverage:** 93,408 records are marked as having a summary. 12,537 of those PDFs can't be downloaded from the FDA, mostly from the early 2000s, so those devices have no outgoing links. About 14,800 predicates cited only by name couldn't be matched to a device and are left out rather than guessed.

## How it was built

1. Download openFDA's 510(k), recall, enforcement and registration records (`pg download`, `pg build-nodes`).
2. For each summary PDF, use the text layer if it's readable, otherwise OCR with Apple's Vision framework (`src/predicate_graph/ingest/`).
3. Ask a model (GLM-5.3-Flash) for every predicate the summary names, with page and quote, into a Pydantic schema (`pg extract-set glm-high`).
4. Keep links whose predicate exists and was cleared earlier (`pg build-edges glm-high`), and match name-only predicates to devices (`pg resolve-names glm-high`).
5. Write the dataset (`uv run python scripts/export_dataset.py`).

Requires Python 3.14, [uv](https://docs.astral.sh/uv/), macOS for OCR, and an API key for the model provider in `.env` (`TOGETHER_API_KEY` or `GLM_API_KEY`).

## License

Code: MIT. Dataset: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). The underlying FDA records are public domain.
