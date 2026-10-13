import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass

from predicate_graph.config import NODES_DB

@dataclass
class Graph:
    parents: dict[str, set[str]] # device -> predicates
    children: dict[str, set[str]] # device -> descendants

def load(include_name_only_edges=True) -> Graph:
    """Build adj graph"""
    conn = sqlite3.connect(NODES_DB)
    rows = conn.execute("SELECT citing, predicate FROM edges WHERE valid = 1").fetchall()
    if include_name_only_edges:
        rows += conn.execute("SELECT citing, predicate FROM edges_name_only").fetchall()
    conn.close()

    parents, children = defaultdict(set), defaultdict(set)
    for citing, predicate in rows:
        parents[citing].add(predicate)
        children[predicate].add(citing)
    return Graph(parents, children)

def _reachable(start: str, step: dict[str, set[str]]) -> set[str]:
    visited = set()
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nnode in step.get(node, set()):
            if nnode not in visited:
                visited.add(nnode)
                queue.append(nnode)
    visited.discard(start)
    return visited

def ancestors(g: Graph, k: str) -> set[str]:
    return _reachable(k, g.parents)

def descendants(g: Graph, k: str) -> set[str]:
    return _reachable(k, g.children)