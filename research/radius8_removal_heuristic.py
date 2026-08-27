#!/usr/bin/env python3
"""Heuristic search for a profitable radius-eight removal mask.

This is deliberately *not* an exact solver.  It searches the 8-subsets of the
fixed record with incremental one-for-one mutations, ranks a mask by how many
outsiders' link graphs it covers, and directly checks whether nine unlocked
outsiders can coexist.  Any positive construction is verified geometrically;
failure to find one is reported only as ``NOT_FOUND``.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import struct
import time
from pathlib import Path

from solver_exchange_sat import (
    build_conflicts,
    load_record,
    squared_distance,
    verify_no_isosceles,
)


Mask = int
Point = tuple[int, int]


def is_isosceles(a: Point, b: Point, c: Point) -> bool:
    ab = squared_distance(a, b)
    ac = squared_distance(a, c)
    bc = squared_distance(b, c)
    return ab == ac or ab == bc or ac == bc


def read_pair_binary(path: Path):
    raw = path.read_bytes()
    offset = 0
    header = struct.Struct("<4sIIII64s")
    magic, n, radius, record_size, candidate_count, digest = header.unpack_from(raw, offset)
    offset += header.size
    if magic != b"RPC1":
        raise ValueError("bad pair-binary magic")
    candidates: list[Point] = []
    covers: list[list[Mask]] = []
    for _ in range(candidate_count):
        x, y, count = struct.unpack_from("<HHI", raw, offset)
        offset += 8
        family = []
        for _ in range(count):
            a, b, c = struct.unpack_from("<QQQ", raw, offset)
            offset += 24
            family.append(a | (b << 64) | (c << 128))
        candidates.append((x, y))
        covers.append(family)
    (required_count,) = struct.unpack_from("<I", raw, offset)
    offset += 4
    required: dict[tuple[int, int], Mask] = {}
    for _ in range(required_count):
        left, right, a, b, c = struct.unpack_from("<IIQQQ", raw, offset)
        offset += 32
        required[(left, right)] = a | (b << 64) | (c << 128)
    if offset != len(raw):
        raise ValueError("trailing pair-binary data")
    return n, radius, record_size, digest.decode("ascii"), candidates, covers, required


def contribution(uncovered: int) -> int:
    # Exact unlocks dominate, while near-covered link graphs guide plateau moves.
    return 100_000 if uncovered == 0 else 1_000 if uncovered == 1 else 10 if uncovered == 2 else 0


def compatible_nine(
    unlocked: list[int],
    candidates: list[Point],
    required: dict[tuple[int, int], Mask],
    removal: Mask,
    target: int,
) -> list[int] | None:
    if len(unlocked) < target:
        return None
    adjacency: dict[int, set[int]] = {p: set() for p in unlocked}
    for offset, left in enumerate(unlocked):
        for right in unlocked[offset + 1 :]:
            key = (left, right) if left < right else (right, left)
            forced = required.get(key, 0)
            if forced & ~removal == 0:
                adjacency[left].add(right)
                adjacency[right].add(left)

    ordered = sorted(unlocked, key=lambda p: len(adjacency[p]), reverse=True)

    def search(chosen: list[int], available: list[int]) -> list[int] | None:
        if len(chosen) == target:
            return chosen.copy()
        if len(chosen) + len(available) < target:
            return None
        while available:
            if len(chosen) + len(available) < target:
                return None
            vertex = available.pop(0)
            if all(vertex in adjacency[old] for old in chosen) and all(
                not is_isosceles(candidates[vertex], candidates[a], candidates[b])
                for i, a in enumerate(chosen)
                for b in chosen[i + 1 :]
            ):
                future = [q for q in available if q in adjacency[vertex]]
                result = search(chosen + [vertex], future)
                if result is not None:
                    return result
        return None

    return search([], ordered)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--seed", type=int, default=20260827)
    parser.add_argument("--target", type=int, default=9)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    n, radius, record_size, _, candidates, covers, required = read_pair_binary(args.input)
    record = load_record(n)
    if len(record) != record_size or radius != 8:
        raise ValueError("this heuristic expects the radius-eight S100 instance")
    outside, all_conflicts, _ = build_conflicts(record, n)
    by_point = {point: edges for point, edges in zip(outside, all_conflicts)}
    edges = [[(int(a), int(b)) for a, b in by_point[p]] for p in candidates]

    affected: list[set[int]] = [set() for _ in record]
    for candidate, family in enumerate(edges):
        for a, b in family:
            affected[a].add(candidate)
            affected[b].add(candidate)
    affected_lists = [tuple(values) for values in affected]

    rng = random.Random(args.seed)
    deadline = time.monotonic() + args.seconds
    full_record_mask = (1 << len(record)) - 1
    best_unlocked: list[int] = []
    best_removal = 0
    iterations = 0
    restarts = 0
    witness: list[int] | None = None

    while time.monotonic() < deadline and witness is None:
        restarts += 1
        # Seeding with a genuine minimal cover avoids spending most restarts in
        # regions that unlock nothing.
        seed_candidate = rng.randrange(len(candidates))
        removal = rng.choice(covers[seed_candidate])
        while removal.bit_count() < radius:
            removal |= 1 << rng.randrange(len(record))

        uncovered = [
            sum(1 for a, b in family if not (removal >> a & 1 or removal >> b & 1))
            for family in edges
        ]
        energy = sum(contribution(value) for value in uncovered)
        stagnation = 0

        while stagnation < 5_000 and time.monotonic() < deadline:
            iterations += 1
            removed_vertices = [i for i in range(len(record)) if removal >> i & 1]
            retained_mask = full_record_mask ^ removal
            added_vertex = rng.randrange(len(record))
            while not (retained_mask >> added_vertex & 1):
                added_vertex = rng.randrange(len(record))
            removed_vertex = rng.choice(removed_vertices)
            trial = removal ^ (1 << removed_vertex) ^ (1 << added_vertex)
            changed = affected[removed_vertex] | affected[added_vertex]
            delta = 0
            updates: list[tuple[int, int]] = []
            for candidate in changed:
                new_value = sum(
                    1 for a, b in edges[candidate] if not (trial >> a & 1 or trial >> b & 1)
                )
                delta += contribution(new_value) - contribution(uncovered[candidate])
                updates.append((candidate, new_value))

            # A small temperature permits movement between nearly identical
            # masks but cools within each restart.
            temperature = max(20.0, 15_000.0 * (1.0 - stagnation / 5_000.0))
            if delta >= 0 or rng.random() < math.exp(delta / temperature):
                removal = trial
                energy += delta
                for candidate, value in updates:
                    uncovered[candidate] = value
                stagnation = 0 if delta > 0 else stagnation + 1
            else:
                stagnation += 1

            current = [i for i, value in enumerate(uncovered) if value == 0]
            if len(current) > len(best_unlocked):
                best_unlocked = current
                best_removal = removal
                witness = compatible_nine(
                    current, candidates, required, removal, args.target
                )
                print(
                    f"best_unlocked={len(current)} iterations={iterations} "
                    f"restarts={restarts} witness={witness is not None}",
                    flush=True,
                )
                if witness is not None:
                    break

    elapsed = args.seconds - max(0.0, deadline - time.monotonic())
    removals = [record[i] for i in range(len(record)) if best_removal >> i & 1]
    unlocked_points = [candidates[i] for i in best_unlocked]
    status = "FOUND" if witness is not None else "NOT_FOUND"
    lines = [
        f"status={status}",
        "exact=False",
        f"n={n}",
        f"radius={radius}",
        f"target_added={args.target}",
        f"seed={args.seed}",
        f"elapsed_seconds={elapsed:.6f}",
        f"iterations={iterations}",
        f"restarts={restarts}",
        f"best_unlocked_count={len(best_unlocked)}",
        f"removals={removals}",
        f"unlocked={unlocked_points}",
    ]
    if witness is not None:
        additions = [candidates[i] for i in witness]
        final = [point for point in record if point not in set(removals)] + additions
        verified = len(final) == len(record) - radius + args.target and verify_no_isosceles(final)
        if not verified:
            raise AssertionError("heuristic witness failed direct geometric verification")
        lines.extend([f"additions={additions}", "direct_geometry_verified=True"])
    args.output.write_text("\n".join(lines) + "\n")
    print(
        f"status={status} best_unlocked={len(best_unlocked)} "
        f"iterations={iterations} output={args.output}"
    )


if __name__ == "__main__":
    main()
