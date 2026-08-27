#!/usr/bin/env python3
"""Exact SAT model for a genuine r-for-k exchange around the 164-point record.

Unlike the earlier "individually unlocked" relaxation, this model also forbids
isosceles triples containing two or three newly added points.  It therefore
decides whether r record points can be removed and k outside points can be
added *simultaneously*.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import itertools
import json
import threading
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
from pysat.card import CardEnc, EncType
from pysat.formula import CNF, IDPool
from pysat.solvers import Solver

from solve_removal_radius_cpsat import enumerate_minimal_covers
from solver_exact_k_sat import add_lex_leq


Point = tuple[int, int]

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "alphaevolve_repository_of_problems/experiments/subsets_of_the_grid_with_no_isosceles_triangles/subsets_of_the_grid_with_no_isosceles_triangles.ipynb"


def load_record(n: int) -> list[Point]:
    notebook = json.loads(NOTEBOOK.read_text())
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    tail = source.split(f"sol_{n} = ", 1)[1]
    return ast.literal_eval(tail[: tail.index("]") + 1])


def build_conflicts(record: list[Point], n: int):
    points = np.asarray(record, dtype=np.int32)
    selected = set(record)
    pair_i, pair_j = np.triu_indices(len(record), 1)
    differences = points[pair_i] - points[pair_j]
    pair_distance = np.sum(differences * differences, axis=1)
    outside = [(x, y) for x in range(n) for y in range(n) if (x, y) not in selected]
    conflicts = []
    total_edges = 0
    for point in outside:
        delta = points - np.asarray(point, dtype=np.int32)
        distance = np.sum(delta * delta, axis=1)
        mask = (
            (distance[pair_i] == distance[pair_j])
            | (distance[pair_i] == pair_distance)
            | (distance[pair_j] == pair_distance)
        )
        edges = np.column_stack((pair_i[mask], pair_j[mask])).astype(np.int16)
        conflicts.append(edges)
        total_edges += len(edges)
    return outside, conflicts, total_edges


def add_available_record_symmetry(
    cnf: CNF, pool: IDPool, removed: list[int], record: list[Point], n: int
) -> int:
    """Add lex leaders only for reflections that really preserve the record."""
    point_set = set(record)
    last = n - 1
    transforms = (
        lambda p: (last - p[0], p[1]),
        lambda p: (p[0], last - p[1]),
        lambda p: (last - p[0], last - p[1]),
    )
    index = {point: i for i, point in enumerate(record)}
    count = 0
    for transform in transforms:
        if {transform(point) for point in record} != point_set:
            continue
        permutation = [index[transform(point)] for point in record]
        add_lex_leq(cnf, pool, removed, [removed[permutation[i]] for i in range(len(record))], count)
        count += 1
    return count


def squared_distance(a: Point, b: Point) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def distance_groups(apex: Point, points: list[Point], skip: int | None = None) -> dict[int, list[int]]:
    groups: dict[int, list[int]] = defaultdict(list)
    for index, point in enumerate(points):
        if index != skip:
            groups[squared_distance(apex, point)].append(index)
    return groups


def verify_no_isosceles(points: list[Point]) -> bool:
    """Independent O(n^3) check of a returned construction."""
    for a, b, c in itertools.combinations(points, 3):
        ab = squared_distance(a, b)
        ac = squared_distance(a, c)
        bc = squared_distance(b, c)
        if ab == ac or ab == bc or ac == bc:
            return False
    return True


def build_exchange_formula(
    n: int,
    radius: int,
    target: int,
    symmetry: bool,
    pair_cache: Path | None = None,
):
    record = load_record(n)
    outside, all_conflicts, total_edges = build_conflicts(record, n)

    # A point that has no vertex cover of size <= radius cannot participate in
    # an exchange at this radius.  This exact preprocessing is also what makes
    # the higher-order hypergraph small enough to encode directly.
    eligible_original_indices: list[int] = []
    eligible_covers: list[list[tuple[int, ...]]] = []
    for candidate_index, edges in enumerate(all_conflicts):
        covers = enumerate_minimal_covers(edges, radius)
        if covers:
            eligible_original_indices.append(candidate_index)
            eligible_covers.append(covers)

    candidates = [outside[i] for i in eligible_original_indices]
    conflicts = [all_conflicts[i] for i in eligible_original_indices]

    pool = IDPool()
    cnf = CNF()
    removed = [pool.id(("remove", i)) for i in range(len(record))]
    added = [pool.id(("add", i)) for i in range(len(candidates))]
    cnf.extend(CardEnc.equals(removed, radius, vpool=pool, encoding=EncType.seqcounter).clauses)
    cnf.extend(CardEnc.equals(added, target, vpool=pool, encoding=EncType.seqcounter).clauses)
    symmetry_count = add_available_record_symmetry(cnf, pool, removed, record, n) if symmetry else 0

    pair_incompatibility_clauses = 0
    if pair_cache is not None:
        cache = json.loads(pair_cache.read_text())
        assert cache["format"] == "radius-pair-compatibility-v1"
        assert cache["n"] == n and cache["radius"] == radius
        assert cache["record_sha256"] == hashlib.sha256(repr(record).encode()).hexdigest()
        assert [tuple(point) for point in cache["eligible_candidates"]] == candidates
        candidate_count = len(candidates)
        compatible = {a * candidate_count + b for a, b in cache["compatible_pairs"]}
        for a in range(candidate_count):
            for b in range(a + 1, candidate_count):
                if a * candidate_count + b not in compatible:
                    cnf.append([-added[a], -added[b]])
                    pair_incompatibility_clauses += 1

    # One outsider + two retained record points.
    one_outsider_clauses = 0
    for y, edges in zip(added, conflicts):
        for a, b in edges:
            cnf.append([-y, removed[int(a)], removed[int(b)]])
            one_outsider_clauses += 1

    # Two outsiders + one retained record point, with the record point as apex.
    two_outsider_clauses = 0
    for record_index, apex in enumerate(record):
        for group in distance_groups(apex, candidates).values():
            for p, q in itertools.combinations(group, 2):
                cnf.append([-added[p], -added[q], removed[record_index]])
                two_outsider_clauses += 1

    # The remaining triples have an outside apex.  Equal-distance groups give
    # both the two-outsider/one-record and all-outsider forbidden triples.
    three_outsider_clauses = 0
    for apex_index, apex in enumerate(candidates):
        candidate_groups = distance_groups(apex, candidates, skip=apex_index)
        record_groups = distance_groups(apex, record)
        for distance, group in candidate_groups.items():
            for other_index in group:
                # Unique apex => no duplicate clause on the integer grid (an
                # integer equilateral triangle does not exist).
                for record_index in record_groups.get(distance, ()):
                    cnf.append(
                        [-added[apex_index], -added[other_index], removed[record_index]]
                    )
                    two_outsider_clauses += 1
            for p, q in itertools.combinations(group, 2):
                cnf.append([-added[apex_index], -added[p], -added[q]])
                three_outsider_clauses += 1

    metadata = {
        "record": record,
        "n": n,
        "outside": outside,
        "all_conflicts": all_conflicts,
        "eligible_original_indices": eligible_original_indices,
        "eligible_covers": eligible_covers,
        "candidates": candidates,
        "conflicts": conflicts,
        "total_edges_all_outside": total_edges,
        "one_outsider_clauses": one_outsider_clauses,
        "two_outsider_clauses": two_outsider_clauses,
        "three_outsider_clauses": three_outsider_clauses,
        "symmetry_count": symmetry_count,
        "pair_incompatibility_clauses": pair_incompatibility_clauses,
    }
    return pool, cnf, removed, added, metadata


def solve(
    n: int,
    radius: int,
    target: int,
    symmetry: bool,
    seconds: float,
    solver_name: str,
    pair_cache: Path | None,
    output: Path,
) -> None:
    started = time.monotonic()
    pool, cnf, removed, added, meta = build_exchange_formula(
        n, radius, target, symmetry, pair_cache
    )
    build_seconds = time.monotonic() - started

    with Solver(name=solver_name, bootstrap_with=cnf.clauses) as solver:
        try:
            solver.set_phases(added)
        except (AttributeError, NotImplementedError):
            pass
        timer = threading.Timer(seconds, solver.interrupt)
        timer.start()
        solve_started = time.monotonic()
        result = solver.solve_limited(expect_interrupt=True)
        solve_seconds = time.monotonic() - solve_started
        timer.cancel()
        try:
            solver.clear_interrupt()
        except NotImplementedError:
            pass
        stats = solver.accum_stats()
        model = solver.get_model() if result is True else None

    status = "SAT" if result is True else "UNSAT" if result is False else "UNKNOWN"
    lines = [
        f"n={n}",
        f"record_size={len(meta['record'])}",
        f"radius_removed={radius}",
        f"target_added={target}",
        f"eligible_outside_candidates={len(meta['candidates'])}",
        f"minimal_covers={sum(map(len, meta['eligible_covers']))}",
        f"one_outsider_clauses={meta['one_outsider_clauses']}",
        f"two_outsider_clauses={meta['two_outsider_clauses']}",
        f"three_outsider_clauses={meta['three_outsider_clauses']}",
        f"pair_incompatibility_clauses={meta['pair_incompatibility_clauses']}",
        f"symmetry_break={symmetry}",
        f"record_symmetries_encoded={meta['symmetry_count']}",
        f"variables={pool.top}",
        f"clauses={len(cnf.clauses)}",
        f"solver={solver_name}",
        f"status={status}",
        f"build_seconds={build_seconds:.6f}",
        f"solve_seconds={solve_seconds:.6f}",
        f"stats={stats}",
    ]

    if model is not None:
        positive = {literal for literal in model if literal > 0}
        removal_indices = {i for i, variable in enumerate(removed) if variable in positive}
        addition_indices = [i for i, variable in enumerate(added) if variable in positive]
        retained = [point for i, point in enumerate(meta["record"]) if i not in removal_indices]
        additions = [meta["candidates"][i] for i in addition_indices]
        final_points = retained + additions
        assert len(removal_indices) == radius
        assert len(additions) == target
        assert len(final_points) == len(meta["record"]) - radius + target
        assert verify_no_isosceles(final_points)
        lines.extend(
            [
                f"removals={[meta['record'][i] for i in sorted(removal_indices)]}",
                f"additions={additions}",
                f"final_size={len(final_points)}",
                "independent_geometry_verification=true",
            ]
        )

    output.write_text("\n".join(lines) + "\n")
    print(
        f"status={status} radius={radius} target={target} candidates={len(meta['candidates'])} "
        f"vars={pool.top} clauses={len(cnf.clauses)} output={output}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(64, 100), default=100)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--symmetry-break", action="store_true")
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--solver", default="glucose42")
    parser.add_argument("--pair-cache", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    solve(
        args.n,
        args.radius,
        args.target,
        args.symmetry_break,
        args.seconds,
        args.solver,
        args.pair_cache,
        args.output,
    )


if __name__ == "__main__":
    main()
