#!/usr/bin/env python3
"""Exact antichain DFS for genuine local exchanges.

The state carried by the search is a family of inclusion-minimal record-removal
masks that can support all currently selected outside points.  When adding a
candidate, each old mask is united with:

* one minimal vertex cover for the candidate's one-outsider conflict graph;
* all record points forced by mixed triples with earlier candidates.

Masks larger than the removal radius are discarded and supersets are removed.
This directly enforces a *common* removal set, unlike pairwise compatibility
alone.  All-outsider isosceles triples are rejected geometrically.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from pathlib import Path

from radius7_pair_compatibility import build_required_masks
from solve_removal_radius_cpsat import enumerate_minimal_covers
from solver_exchange_sat import (
    build_conflicts,
    load_record,
    squared_distance,
    verify_no_isosceles,
)


def is_isosceles(a, b, c) -> bool:
    ab = squared_distance(a, b)
    ac = squared_distance(a, c)
    bc = squared_distance(b, c)
    return ab == ac or ab == bc or ac == bc


def minimize_masks(values: set[int]) -> tuple[int, ...]:
    kept: list[int] = []
    for mask in sorted(values, key=lambda item: (item.bit_count(), item)):
        if not any((old & mask) == old for old in kept):
            kept.append(mask)
    return tuple(kept)


def extend_family(
    family: tuple[int, ...],
    covers: list[int],
    forced: int,
    radius: int,
) -> tuple[int, ...]:
    values: set[int] = set()
    for old in family:
        partial = old | forced
        if partial.bit_count() > radius:
            continue
        for cover in covers:
            new = partial | cover
            if new.bit_count() <= radius:
                values.add(new)
    return minimize_masks(values) if values else ()


def degeneracy_order(adjacency: list[int]) -> list[int]:
    """Smallest-last ordering, used only as a deterministic search heuristic."""
    remaining = set(range(len(adjacency)))
    degree = [(adjacency[v]).bit_count() for v in range(len(adjacency))]
    removed_order: list[int] = []
    while remaining:
        vertex = min(remaining, key=lambda v: (degree[v], v))
        remaining.remove(vertex)
        removed_order.append(vertex)
        neighbors = adjacency[vertex]
        while neighbors:
            bit = neighbors & -neighbors
            other = bit.bit_length() - 1
            neighbors -= bit
            if other in remaining:
                degree[other] -= 1
    return list(reversed(removed_order))


def solve(n: int, radius: int, target: int, pair_cache: Path, seconds: float, output: Path) -> None:
    started = time.monotonic()
    deadline = started + seconds
    record = load_record(n)
    outside, conflicts, _ = build_conflicts(record, n)

    eligible_original_indices = []
    covers: list[list[int]] = []
    for outside_index, edges in enumerate(conflicts):
        candidate_covers = enumerate_minimal_covers(edges, radius)
        if candidate_covers:
            eligible_original_indices.append(outside_index)
            covers.append([sum(1 << vertex for vertex in cover) for cover in candidate_covers])
    candidates = [outside[index] for index in eligible_original_indices]

    cache = json.loads(pair_cache.read_text())
    expected_hash = hashlib.sha256(repr(record).encode()).hexdigest()
    assert cache["format"] == "radius-pair-compatibility-v1"
    assert cache["n"] == n and cache["radius"] == radius
    assert cache["record_sha256"] == expected_hash
    assert [tuple(point) for point in cache["eligible_candidates"]] == candidates

    adjacency = [0] * len(candidates)
    for a, b in cache["compatible_pairs"]:
        adjacency[a] |= 1 << b
        adjacency[b] |= 1 << a
    forced_pairs = build_required_masks(record, candidates)

    # Relabel by a clique-friendly smallest-last ordering.  This changes only
    # traversal order, never the represented candidate set.
    order = degeneracy_order(adjacency)
    old_to_new = {old: new for new, old in enumerate(order)}
    rel_candidates = [candidates[old] for old in order]
    rel_covers = [covers[old] for old in order]
    rel_adjacency = [0] * len(order)
    for new, old in enumerate(order):
        bits = adjacency[old]
        while bits:
            bit = bits & -bits
            neighbor_old = bit.bit_length() - 1
            bits -= bit
            rel_adjacency[new] |= 1 << old_to_new[neighbor_old]
    rel_forced = {}
    for (a, b), mask in forced_pairs.items():
        x, y = sorted((old_to_new[a], old_to_new[b]))
        rel_forced[(x, y)] = mask

    nodes = 0
    family_extensions = 0
    masks_generated = 0
    pruned_cardinality = 0
    pruned_removals = 0
    pruned_outside_triples = 0
    timed_out = False
    witness_selected: list[int] | None = None
    witness_family: tuple[int, ...] | None = None

    def dfs(selected: list[int], family: tuple[int, ...], possible: int) -> bool:
        nonlocal nodes, family_extensions, masks_generated
        nonlocal pruned_cardinality, pruned_removals, pruned_outside_triples
        nonlocal timed_out, witness_selected, witness_family
        nodes += 1
        if nodes % 4096 == 0 and time.monotonic() >= deadline:
            timed_out = True
            return False
        if len(selected) >= target:
            witness_selected = selected[:]
            witness_family = family
            return True
        need = target - len(selected)
        if possible.bit_count() < need:
            pruned_cardinality += 1
            return False

        # Canonical increasing-index enumeration: after considering v, only
        # larger remaining vertices are passed to its child.
        remaining = possible
        while remaining:
            if timed_out:
                return False
            bit = remaining & -remaining
            vertex = bit.bit_length() - 1
            remaining -= bit
            if 1 + remaining.bit_count() < need:
                pruned_cardinality += 1
                return False

            triple_bad = False
            for offset, left in enumerate(selected):
                for right in selected[offset + 1 :]:
                    if is_isosceles(rel_candidates[left], rel_candidates[right], rel_candidates[vertex]):
                        triple_bad = True
                        break
                if triple_bad:
                    break
            if triple_bad:
                pruned_outside_triples += 1
                continue

            forced = 0
            for old in selected:
                forced |= rel_forced.get((min(old, vertex), max(old, vertex)), 0)
            next_family = extend_family(family, rel_covers[vertex], forced, radius)
            family_extensions += 1
            masks_generated += len(next_family)
            if not next_family:
                pruned_removals += 1
                continue

            next_possible = remaining & rel_adjacency[vertex]
            # Any future point must also avoid an all-outsider isosceles triple
            # with vertex and each previously selected point.
            filtered = next_possible
            scan = filtered
            while scan:
                future_bit = scan & -scan
                future = future_bit.bit_length() - 1
                scan -= future_bit
                if any(
                    is_isosceles(rel_candidates[old], rel_candidates[vertex], rel_candidates[future])
                    for old in selected
                ):
                    filtered -= future_bit
            if len(selected) + 1 + filtered.bit_count() < target:
                pruned_cardinality += 1
                continue
            if dfs(selected + [vertex], next_family, filtered):
                return True
        return False

    found = dfs([], (0,), (1 << len(candidates)) - 1)
    elapsed = time.monotonic() - started
    status = "SAT" if found else "UNKNOWN" if timed_out else "UNSAT"
    lines = [
        f"n={n}",
        f"record_size={len(record)}",
        f"radius_removed={radius}",
        f"target_added={target}",
        f"eligible_candidates={len(candidates)}",
        f"compatible_pairs={cache['compatible_pair_count']}",
        f"status={status}",
        f"nodes={nodes}",
        f"family_extensions={family_extensions}",
        f"masks_generated={masks_generated}",
        f"pruned_cardinality={pruned_cardinality}",
        f"pruned_removals={pruned_removals}",
        f"pruned_outside_triples={pruned_outside_triples}",
        f"elapsed_seconds={elapsed:.6f}",
    ]
    if found:
        assert witness_selected is not None and witness_family
        removal_mask = witness_family[0]
        # Pad to exactly radius removals; deletion preserves validity.
        for vertex in range(len(record)):
            if removal_mask.bit_count() == radius:
                break
            removal_mask |= 1 << vertex
        removals = [i for i in range(len(record)) if removal_mask >> i & 1]
        additions = [rel_candidates[i] for i in witness_selected]
        final_points = [point for i, point in enumerate(record) if i not in removals] + additions
        assert len(removals) == radius and len(additions) == target
        assert verify_no_isosceles(final_points)
        lines.extend(
            [
                f"removals={[record[i] for i in removals]}",
                f"additions={additions}",
                f"final_size={len(final_points)}",
                "independent_geometry_verification=true",
            ]
        )
    output.write_text("\n".join(lines) + "\n")
    print(f"status={status} n={n} radius={radius} target={target} nodes={nodes} output={output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(64, 100), default=100)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--pair-cache", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    solve(args.n, args.radius, args.target, args.pair_cache, args.seconds, args.output)


if __name__ == "__main__":
    main()
