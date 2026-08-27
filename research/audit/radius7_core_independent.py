#!/usr/bin/env python3
"""Independent checker for the radius-7, target-6 core/triple preprocessing.

This checker imports no production radius-7 module.  It uses a queue-based
k-core peel (rather than the production batch peel), direct three-distance
geometry for forced record masks, and independently generated minimal covers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import deque
from pathlib import Path

from independent_cnf import (
    alternative_minimal_covers,
    build_conflicts,
    load_record,
    squared_distance,
    validate_record,
)


def queue_core(adjacency: list[set[int]], minimum_degree: int) -> list[int]:
    active = [True] * len(adjacency)
    degree = [len(neighbors) for neighbors in adjacency]
    queue = deque(index for index, value in enumerate(degree) if value < minimum_degree)
    while queue:
        vertex = queue.popleft()
        if not active[vertex] or degree[vertex] >= minimum_degree:
            continue
        active[vertex] = False
        for neighbor in adjacency[vertex]:
            if active[neighbor]:
                degree[neighbor] -= 1
                if degree[neighbor] == minimum_degree - 1:
                    queue.append(neighbor)
    return [index for index, present in enumerate(active) if present]


def antichain(masks) -> tuple[int, ...]:
    kept: list[int] = []
    for mask in sorted(set(masks), key=lambda value: (value.bit_count(), value)):
        if all(old & mask != old for old in kept):
            kept.append(mask)
    return tuple(kept)


def forced_mask(left, right, record) -> int:
    pair_distance = squared_distance(left, right)
    mask = 0
    for index, point in enumerate(record):
        left_distance = squared_distance(left, point)
        right_distance = squared_distance(right, point)
        if (
            left_distance == right_distance
            or left_distance == pair_distance
            or right_distance == pair_distance
        ):
            mask |= 1 << index
    return mask


def is_isosceles(a, b, c) -> bool:
    ab = squared_distance(a, b)
    ac = squared_distance(a, c)
    bc = squared_distance(b, c)
    return ab == ac or ab == bc or ac == bc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("cache", type=Path)
    parser.add_argument("--target", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    radius = 7

    raw = args.cache.read_bytes()
    cache = json.loads(raw)
    if cache["n"] != 100 or cache["radius"] != radius:
        raise ValueError("expected n=100, radius=7 cache")

    record = load_record()
    validate_record(record)
    outside, conflicts = build_conflicts(record)
    eligible_points = []
    eligible_covers = []
    eligible_edges = []
    for point, edges in zip(outside, conflicts):
        covers = alternative_minimal_covers(edges, radius)
        if covers:
            eligible_points.append(point)
            eligible_covers.append(
                [sum(1 << vertex for vertex in cover) for cover in sorted(covers)]
            )
            eligible_edges.append(edges)
    assert eligible_points == [tuple(point) for point in cache["eligible_candidates"]]

    adjacency = [set() for _ in eligible_points]
    for left, right in cache["compatible_pairs"]:
        adjacency[left].add(right)
        adjacency[right].add(left)
    core_old = queue_core(adjacency, args.target - 1)
    old_to_new = {old: new for new, old in enumerate(core_old)}
    candidates = [eligible_points[old] for old in core_old]
    covers = [eligible_covers[old] for old in core_old]
    core_edges_for_points = [eligible_edges[old] for old in core_old]
    core_adjacency = [set() for _ in core_old]
    for new, old in enumerate(core_old):
        core_adjacency[new] = {
            old_to_new[neighbor]
            for neighbor in adjacency[old]
            if neighbor in old_to_new
        }
    core_edge_count = sum(map(len, core_adjacency)) // 2

    direct_forced = {}
    forced_entries_all_core_pairs = 0
    for left in range(len(candidates)):
        for right in range(left + 1, len(candidates)):
            mask = forced_mask(candidates[left], candidates[right], record)
            forced_entries_all_core_pairs += mask.bit_count()
            if right in core_adjacency[left]:
                direct_forced[(left, right)] = mask

    pair_families = {}
    for left in range(len(candidates)):
        for right in core_adjacency[left]:
            if left >= right:
                continue
            forced = direct_forced[(left, right)]
            pair_families[(left, right)] = antichain(
                first | second | forced
                for first in covers[left]
                for second in covers[right]
                if (first | second | forced).bit_count() <= radius
            )
            assert pair_families[(left, right)]

    triangles_tested = 0
    incompatible_triples = 0
    geometry_incompatible = 0
    removal_incompatible = 0
    for left in range(len(candidates)):
        for middle in sorted(vertex for vertex in core_adjacency[left] if vertex > left):
            for right in sorted(
                vertex
                for vertex in core_adjacency[left].intersection(core_adjacency[middle])
                if vertex > middle
            ):
                triangles_tested += 1
                if is_isosceles(candidates[left], candidates[middle], candidates[right]):
                    incompatible_triples += 1
                    geometry_incompatible += 1
                    continue
                extra = (
                    direct_forced[(left, right)]
                    | direct_forced[(middle, right)]
                )
                feasible = any(
                    (pair_mask | extra | cover).bit_count() <= radius
                    for pair_mask in pair_families[(left, middle)]
                    for cover in covers[right]
                )
                if not feasible:
                    incompatible_triples += 1
                    removal_incompatible += 1

    result = {
        "status": "VERIFIED",
        "cache_sha256": hashlib.sha256(raw).hexdigest(),
        "minimum_core_degree": args.target - 1,
        "eligible_candidates": len(eligible_points),
        "core_candidates": len(candidates),
        "core_compatible_edges": core_edge_count,
        "one_outsider_clauses": sum(map(len, core_edges_for_points)),
        "two_outsider_forced_entries": forced_entries_all_core_pairs,
        "triangles_tested": triangles_tested,
        "triple_incompatibilities": incompatible_triples,
        "geometry_incompatible_triples": geometry_incompatible,
        "removal_incompatible_triples": removal_incompatible,
        "elapsed_seconds": time.monotonic() - started,
    }
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
