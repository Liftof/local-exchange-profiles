#!/usr/bin/env python3
"""Find a maximum clique in an exact pair-compatibility graph.

The input is produced by ``radius7_pair_compatibility.py``.  A clique is only
a necessary condition for a simultaneous exchange: this program never claims
that all members of a clique admit one common removal set.  Conversely, every
genuine exchange is a clique, so a clique upper bound is a rigorous exchange
upper bound.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path


def greedy_coloring(vertices: int, adjacency: list[int]) -> tuple[list[int], list[int]]:
    """Return a greedy color order and nondecreasing clique upper bounds."""
    order: list[int] = []
    bounds: list[int] = []
    remaining = vertices
    color = 0
    while remaining:
        color += 1
        available = remaining
        while available:
            bit = available & -available
            vertex = bit.bit_length() - 1
            order.append(vertex)
            bounds.append(color)
            remaining ^= bit
            available ^= bit
            available &= ~adjacency[vertex]
    return order, bounds


def maximum_clique(adjacency: list[int]) -> tuple[list[int], int]:
    best: list[int] = []
    nodes = 0

    def expand(chosen: list[int], candidates: int) -> None:
        nonlocal best, nodes
        nodes += 1
        order, bounds = greedy_coloring(candidates, adjacency)
        for offset in range(len(order) - 1, -1, -1):
            if len(chosen) + bounds[offset] <= len(best):
                return
            vertex = order[offset]
            bit = 1 << vertex
            if not candidates & bit:
                continue
            chosen.append(vertex)
            next_candidates = candidates & adjacency[vertex]
            if next_candidates:
                expand(chosen, next_candidates)
            elif len(chosen) > len(best):
                best = chosen.copy()
            chosen.pop()
            candidates ^= bit

    expand([], (1 << len(adjacency)) - 1)
    return best, nodes


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    raw = args.input.read_bytes()
    payload = json.loads(raw)
    count = payload["eligible_candidate_count"]
    adjacency = [0] * count
    for left, right in payload["compatible_pairs"]:
        adjacency[left] |= 1 << right
        adjacency[right] |= 1 << left

    started = time.monotonic()
    clique, search_nodes = maximum_clique(adjacency)
    elapsed = time.monotonic() - started
    for i, left in enumerate(clique):
        for right in clique[i + 1 :]:
            assert adjacency[left] & (1 << right)

    result = {
        "format": "pair-compatibility-maximum-clique-v1",
        "input": str(args.input),
        "input_sha256": hashlib.sha256(raw).hexdigest(),
        "n": payload["n"],
        "radius": payload["radius"],
        "vertices": count,
        "edges": payload["compatible_pair_count"],
        "maximum_clique_size": len(clique),
        "maximum_clique_indices": clique,
        "maximum_clique_points": [payload["eligible_candidates"][i] for i in clique],
        "search_nodes": search_nodes,
        "solve_seconds": elapsed,
        "warning": "Pairwise compatibility is necessary, not sufficient, for a joint exchange.",
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
