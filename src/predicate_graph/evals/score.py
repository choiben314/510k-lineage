import json
import csv
from pathlib import Path

from predicate_graph.config import LABELS, OUT_DIR

from sklearn.metrics import precision_recall_fscore_support
from sklearn.preprocessing import MultiLabelBinarizer

GOLD_PATH = LABELS / "gold.jsonl"
SAMPLE_PATH = LABELS / "eval_sample.csv"

def load_jsonl(path: Path) -> dict[str, dict]:
    return{r["k_number"]: r for r in (json.loads(l) for l in open(path))}

def score(labels: dict, predictions: dict, doc_ids: list[str]) -> dict:
    label_predicates = {k for doc in doc_ids for k in labels[doc]["predicates"]}
    prediction_predicates = {
        c["k_number"] for doc in doc_ids for c in predictions.get(doc, {}).get("predicates", [])
    }

    all_predicates = label_predicates | prediction_predicates

    mlb = MultiLabelBinarizer(classes=sorted(all_predicates))
    y_true = mlb.fit_transform([labels[doc]["predicates"] for doc in doc_ids])
    y_pred = mlb.transform([
        [c["k_number"] for c in predictions.get(doc, {}).get("predicates", [])] for doc in doc_ids
    ])

    micro_p, micro_r, micro_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="micro", zero_division=1)
    doc_p, doc_r, doc_f1, _ = precision_recall_fscore_support(y_true, y_pred, average="samples", zero_division=1)

    return {
        "micro_p": micro_p, "micro_r": micro_r, "micro_f1": micro_f1,
        "doc_p": doc_p, "doc_r": doc_r, "doc_f1": doc_f1,
    }

def score_by_group(labels: dict, predictions: dict, doc_ids: list[str], groups: dict) -> None:
    doc_groups = sorted({groups[doc] for doc in doc_ids if doc in groups})
    group_scores = {}
    for group in doc_groups:
        group_docs = [doc for doc in doc_ids if groups.get(doc) == group]
        s = score(labels, predictions, group_docs)
        group_scores[group] = s
    return group_scores

def score_model(model: str) -> None:
    gold = load_jsonl(GOLD_PATH)
    doc_ids = sorted(gold)

    preds = load_jsonl(OUT_DIR / f"{model}.jsonl")
    s = score(gold, preds, doc_ids)
    print(json.dumps(s, indent=4))

    # Score by decade groups
    groups_decade = {}
    if SAMPLE_PATH.exists():
        for row in csv.DictReader(open(SAMPLE_PATH)):
            groups_decade[row["k_number"]] = row.get("decade", "")
    decade_scores = score_by_group(gold, preds, doc_ids, groups_decade)
    print(json.dumps(decade_scores, indent=4))