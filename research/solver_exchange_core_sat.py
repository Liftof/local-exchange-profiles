#!/usr/bin/env python3
"""Core-pruned SAT confirmation for exact local exchanges.

Any k simultaneous additions form a K_k in the exact pair-compatibility graph,
so every selected vertex lies in its (k-1)-core.  This necessary condition is
used before building the CNF.  Optional ternary preprocessing also rejects
pairwise-compatible triples that have no common removal mask of size r.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import threading
import time
from pathlib import Path

from pysat.card import CardEnc, EncType
from pysat.formula import CNF, IDPool
from pysat.solvers import Solver

from radius7_pair_compatibility import build_required_masks
from radius7_exchange_dfs import is_isosceles, minimize_masks
from solve_removal_radius_cpsat import enumerate_minimal_covers
from solver_exchange_sat import (
    add_available_record_symmetry,
    build_conflicts,
    distance_groups,
    load_record,
    verify_no_isosceles,
)


def k_core(adjacency: list[int], minimum_degree: int) -> list[int]:
    active = (1 << len(adjacency)) - 1
    changed = True
    while changed:
        changed = False
        scan = active
        remove = 0
        while scan:
            bit = scan & -scan
            vertex = bit.bit_length() - 1
            scan -= bit
            if (adjacency[vertex] & active).bit_count() < minimum_degree:
                remove |= bit
        if remove:
            active &= ~remove
            changed = True
    return [vertex for vertex in range(len(adjacency)) if active >> vertex & 1]


def pair_mask_family(left: list[int], right: list[int], forced: int, radius: int) -> tuple[int, ...]:
    values = {
        a | b | forced
        for a in left
        for b in right
        if (a | b | forced).bit_count() <= radius
    }
    return minimize_masks(values)


def solve(
    n: int,
    radius: int,
    target: int,
    pair_cache: Path,
    triple_compatibility: bool,
    symmetry: bool,
    seconds: float,
    solver_name: str,
    output: Path,
) -> None:
    started = time.monotonic()
    record = load_record(n)
    outside, all_conflicts, _ = build_conflicts(record, n)
    eligible_indices = []
    eligible_covers = []
    for outside_index, edges in enumerate(all_conflicts):
        covers = enumerate_minimal_covers(edges, radius)
        if covers:
            eligible_indices.append(outside_index)
            eligible_covers.append([sum(1 << vertex for vertex in cover) for cover in covers])
    eligible_points = [outside[index] for index in eligible_indices]

    cache = json.loads(pair_cache.read_text())
    assert cache["format"] == "radius-pair-compatibility-v1"
    assert cache["n"] == n and cache["radius"] == radius
    assert cache["record_sha256"] == hashlib.sha256(repr(record).encode()).hexdigest()
    assert [tuple(point) for point in cache["eligible_candidates"]] == eligible_points

    adjacency = [0] * len(eligible_points)
    for a, b in cache["compatible_pairs"]:
        adjacency[a] |= 1 << b
        adjacency[b] |= 1 << a
    core_old = k_core(adjacency, target - 1)
    old_to_core = {old: new for new, old in enumerate(core_old)}
    candidates = [eligible_points[old] for old in core_old]
    covers = [eligible_covers[old] for old in core_old]
    conflicts = [all_conflicts[eligible_indices[old]] for old in core_old]
    core_adjacency = [0] * len(core_old)
    core_edges = 0
    for new, old in enumerate(core_old):
        bits = adjacency[old]
        while bits:
            bit = bits & -bits
            other_old = bit.bit_length() - 1
            bits -= bit
            if other_old in old_to_core:
                core_adjacency[new] |= 1 << old_to_core[other_old]
        core_edges += core_adjacency[new].bit_count()
    core_edges //= 2

    pool, cnf = IDPool(), CNF()
    removed = [pool.id(("remove", i)) for i in range(len(record))]
    added = [pool.id(("add", i)) for i in range(len(candidates))]
    cnf.extend(CardEnc.equals(removed, radius, vpool=pool, encoding=EncType.seqcounter).clauses)
    cnf.extend(CardEnc.equals(added, target, vpool=pool, encoding=EncType.seqcounter).clauses)
    symmetry_count = add_available_record_symmetry(cnf, pool, removed, record, n) if symmetry else 0

    one_outsider = 0
    for y, edges in zip(added, conflicts):
        for a, b in edges:
            cnf.append([-y, removed[int(a)], removed[int(b)]])
            one_outsider += 1

    pair_incompatible = 0
    for a in range(len(candidates)):
        for b in range(a + 1, len(candidates)):
            if not (core_adjacency[a] >> b & 1):
                cnf.append([-added[a], -added[b]])
                pair_incompatible += 1

    two_outsider = 0
    for record_index, apex in enumerate(record):
        for group in distance_groups(apex, candidates).values():
            for a, b in itertools.combinations(group, 2):
                cnf.append([-added[a], -added[b], removed[record_index]])
                two_outsider += 1
    for apex_index, apex in enumerate(candidates):
        candidate_groups = distance_groups(apex, candidates, skip=apex_index)
        record_groups = distance_groups(apex, record)
        for distance, group in candidate_groups.items():
            for other in group:
                for record_index in record_groups.get(distance, ()):
                    cnf.append([-added[apex_index], -added[other], removed[record_index]])
                    two_outsider += 1

    three_outsider_geometry = 0
    for apex_index, apex in enumerate(candidates):
        for group in distance_groups(apex, candidates, skip=apex_index).values():
            for a, b in itertools.combinations(group, 2):
                cnf.append([-added[apex_index], -added[a], -added[b]])
                three_outsider_geometry += 1

    triple_incompatible = 0
    triangles_tested = 0
    if triple_compatibility:
        forced = build_required_masks(record, candidates)
        pair_families = {}
        for a in range(len(candidates)):
            neighbors = core_adjacency[a] & ~((1 << (a + 1)) - 1)
            while neighbors:
                bit = neighbors & -neighbors
                b = bit.bit_length() - 1
                neighbors -= bit
                pair_families[(a, b)] = pair_mask_family(
                    covers[a], covers[b], forced.get((a, b), 0), radius
                )
        for a in range(len(candidates)):
            higher = core_adjacency[a] & ~((1 << (a + 1)) - 1)
            scan = higher
            while scan:
                bit = scan & -scan
                b = bit.bit_length() - 1
                scan -= bit
                common = higher & core_adjacency[b] & ~((1 << (b + 1)) - 1)
                while common:
                    cbit = common & -common
                    c = cbit.bit_length() - 1
                    common -= cbit
                    triangles_tested += 1
                    feasible = False
                    if not is_isosceles(candidates[a], candidates[b], candidates[c]):
                        extra = forced.get((a, c), 0) | forced.get((b, c), 0)
                        for pair_mask in pair_families[(a, b)]:
                            partial = pair_mask | extra
                            if partial.bit_count() > radius:
                                continue
                            if any((partial | cover).bit_count() <= radius for cover in covers[c]):
                                feasible = True
                                break
                    if not feasible:
                        cnf.append([-added[a], -added[b], -added[c]])
                        triple_incompatible += 1

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
        f"n={n}", f"record_size={len(record)}", f"radius_removed={radius}",
        f"target_added={target}", f"eligible_candidates={len(eligible_points)}",
        f"core_candidates={len(candidates)}", f"core_compatible_edges={core_edges}",
        f"one_outsider_clauses={one_outsider}", f"two_outsider_clauses={two_outsider}",
        f"three_outsider_geometry_clauses={three_outsider_geometry}",
        f"pair_incompatibility_clauses={pair_incompatible}",
        f"triple_compatibility={triple_compatibility}", f"triangles_tested={triangles_tested}",
        f"triple_incompatibility_clauses={triple_incompatible}",
        f"symmetry_break={symmetry}", f"record_symmetries_encoded={symmetry_count}",
        f"variables={pool.top}", f"clauses={len(cnf.clauses)}", f"solver={solver_name}",
        f"status={status}", f"build_seconds={build_seconds:.6f}",
        f"solve_seconds={solve_seconds:.6f}", f"stats={stats}",
    ]
    if model is not None:
        positive = {literal for literal in model if literal > 0}
        removal_indices = [i for i, variable in enumerate(removed) if variable in positive]
        additions = [candidates[i] for i, variable in enumerate(added) if variable in positive]
        final_points = [p for i, p in enumerate(record) if i not in removal_indices] + additions
        assert len(removal_indices) == radius and len(additions) == target
        assert verify_no_isosceles(final_points)
        lines.extend([f"removals={[record[i] for i in removal_indices]}", f"additions={additions}",
                      f"final_size={len(final_points)}", "independent_geometry_verification=true"])
    output.write_text("\n".join(lines) + "\n")
    print(f"status={status} core={len(candidates)} triangles={triangles_tested} output={output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, choices=(64, 100), default=100)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--pair-cache", type=Path, required=True)
    parser.add_argument("--triple-compatibility", action="store_true")
    parser.add_argument("--symmetry-break", action="store_true")
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--solver", default="glucose42")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    solve(args.n, args.radius, args.target, args.pair_cache, args.triple_compatibility,
          args.symmetry_break, args.seconds, args.solver, args.output)


if __name__ == "__main__":
    main()
