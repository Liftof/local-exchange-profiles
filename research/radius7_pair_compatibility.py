#!/usr/bin/env python3
"""Precompute exact pair compatibility for the radius-7 exchange SAT model.

Two outside candidates p and q are compatible at radius r iff some r-element
removal set simultaneously:

* contains a vertex cover of each one-outsider conflict graph; and
* removes every record point that forms an isosceles triple with p and q.

The output stores only compatible pairs.  Every omitted pair therefore yields
the valid redundant SAT clause ``not add_p or not add_q``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing as mp
import time
from collections import defaultdict
from pathlib import Path

from solve_removal_radius_cpsat import enumerate_minimal_covers
from solver_exchange_sat import build_conflicts, distance_groups, load_record


_COVERS: list[list[int]] = []
_REQUIRED: dict[tuple[int, int], int] = {}
_RADIUS = 0


def pair_compatible(i: int, j: int) -> bool:
    fixed = _REQUIRED.get((i, j), 0)
    if fixed.bit_count() > _RADIUS:
        return False
    left, right = _COVERS[i], _COVERS[j]
    # Put the shorter family outside the nested loop.
    if len(left) > len(right):
        left, right = right, left
    for a in left:
        partial = a | fixed
        if partial.bit_count() > _RADIUS:
            continue
        for b in right:
            if (partial | b).bit_count() <= _RADIUS:
                return True
    return False


def process_rows(bounds: tuple[int, int]) -> tuple[list[tuple[int, int]], int]:
    start, stop = bounds
    compatible: list[tuple[int, int]] = []
    tested = 0
    for i in range(start, stop):
        for j in range(i + 1, len(_COVERS)):
            tested += 1
            if pair_compatible(i, j):
                compatible.append((i, j))
    return compatible, tested


def build_required_masks(record, candidates):
    required: dict[tuple[int, int], int] = defaultdict(int)

    # Record apex, two outside endpoints.
    for record_index, apex in enumerate(record):
        for group in distance_groups(apex, candidates).values():
            for offset, p in enumerate(group):
                for q in group[offset + 1 :]:
                    required[(min(p, q), max(p, q))] |= 1 << record_index

    # Outside apex, one outside endpoint and one record endpoint.
    for apex_index, apex in enumerate(candidates):
        candidate_groups = distance_groups(apex, candidates, skip=apex_index)
        record_groups = distance_groups(apex, record)
        for distance, group in candidate_groups.items():
            record_indices = record_groups.get(distance, ())
            if not record_indices:
                continue
            mask = sum(1 << index for index in record_indices)
            for other_index in group:
                key = (min(apex_index, other_index), max(apex_index, other_index))
                required[key] |= mask
    return dict(required)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(64, 100), default=100)
    parser.add_argument("--radius", type=int, default=7)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--rows-per-task", type=int, default=16)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    started = time.monotonic()
    record = load_record(args.n)
    outside, conflicts, _ = build_conflicts(record, args.n)
    eligible_indices = []
    cover_masks = []
    for outside_index, edges in enumerate(conflicts):
        covers = enumerate_minimal_covers(edges, args.radius)
        if covers:
            eligible_indices.append(outside_index)
            cover_masks.append([sum(1 << vertex for vertex in cover) for cover in covers])
    candidates = [outside[index] for index in eligible_indices]
    required = build_required_masks(record, candidates)

    global _COVERS, _REQUIRED, _RADIUS
    _COVERS = cover_masks
    _REQUIRED = required
    _RADIUS = args.radius

    bounds = [
        (start, min(start + args.rows_per_task, len(candidates)))
        for start in range(0, len(candidates), args.rows_per_task)
    ]
    compatible_pairs: list[tuple[int, int]] = []
    tested = 0
    # Linux/fork preserves the read-only bit-mask tables without serializing a
    # private copy for every task.
    context = mp.get_context("fork")
    with context.Pool(processes=args.workers) as pool:
        for pairs, count in pool.imap_unordered(process_rows, bounds):
            compatible_pairs.extend(pairs)
            tested += count

    compatible_pairs.sort()
    payload = {
        "format": "radius-pair-compatibility-v1",
        "n": args.n,
        "radius": args.radius,
        "record_size": len(record),
        "record_sha256": hashlib.sha256(repr(record).encode()).hexdigest(),
        "eligible_candidates": candidates,
        "eligible_candidate_count": len(candidates),
        "pairs_tested": tested,
        "compatible_pair_count": len(compatible_pairs),
        "incompatible_pair_count": tested - len(compatible_pairs),
        "pairs_with_forced_record_removals": len(required),
        "compatible_pairs": compatible_pairs,
        "build_seconds": time.monotonic() - started,
    }
    args.output.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(
        f"candidates={len(candidates)} tested={tested} compatible={len(compatible_pairs)} "
        f"incompatible={tested-len(compatible_pairs)} output={args.output}"
    )


if __name__ == "__main__":
    main()
