#!/usr/bin/env python3
"""Direct SAT decision model for local replacement around the 164-point record."""

import argparse
import threading
import time
from pathlib import Path

from pysat.card import CardEnc, EncType
from pysat.formula import CNF, IDPool
from pysat.solvers import Solver

from solve_removal_radius_cpsat import build_conflicts, enumerate_minimal_covers, load_record


def add_lex_leq(cnf, pool, left, right, label):
    """Require left <= right lexicographically using exact prefix-equality flags."""
    prefix_equal = pool.id(("lex_equal", label, 0))
    cnf.append([prefix_equal])
    for index, (a, b) in enumerate(zip(left, right)):
        cnf.append([-prefix_equal, -a, b])
        next_equal = pool.id(("lex_equal", label, index + 1))
        cnf.append([-next_equal, prefix_equal])
        cnf.append([-next_equal, -a, b])
        cnf.append([-next_equal, a, -b])
        cnf.append([-prefix_equal, -a, -b, next_equal])
        cnf.append([-prefix_equal, a, b, next_equal])
        prefix_equal = next_equal


def add_grid_symmetry_breaking(cnf, pool, removed, record, n):
    point_index = {point: index for index, point in enumerate(record)}
    transforms = (
        lambda point: (n - 1 - point[0], point[1]),
        lambda point: (point[0], n - 1 - point[1]),
        lambda point: (n - 1 - point[0], n - 1 - point[1]),
    )
    for label, transform in enumerate(transforms):
        if not all(transform(point) in point_index for point in record):
            continue
        permutation = [point_index[transform(point)] for point in record]
        add_lex_leq(
            cnf,
            pool,
            removed,
            [removed[permutation[index]] for index in range(len(record))],
            label,
        )


def solve(
    n,
    radius,
    target,
    encoding,
    symmetry_break,
    seconds,
    solver_name,
    output,
    record_json=None,
):
    started = time.monotonic()
    record = load_record(n, record_json)
    outside, conflicts, total_edges = build_conflicts(record, n)
    pool, cnf = IDPool(), CNF()
    removed = [pool.id(("remove", i)) for i in range(len(record))]
    cnf.extend(CardEnc.equals(removed, radius, vpool=pool, encoding=EncType.seqcounter).clauses)
    if symmetry_break:
        add_grid_symmetry_breaking(cnf, pool, removed, record, n)

    unlocked_variables = []
    total_covers = 0
    for candidate_index, edges in enumerate(conflicts):
        covers = enumerate_minimal_covers(edges, radius)
        if not covers:
            continue
        unlocked = pool.id(("unlocked", candidate_index))
        unlocked_variables.append(unlocked)
        if encoding == "edge":
            for a, b in edges:
                cnf.append([-unlocked, removed[int(a)], removed[int(b)]])
            total_covers += len(covers)
            continue
        cover_variables = []
        for cover_index, cover in enumerate(covers):
            active = pool.id(("cover", candidate_index, cover_index))
            cover_variables.append(active)
            total_covers += 1
            for vertex in cover:
                cnf.append([-active, removed[vertex]])
            cnf.append([-removed[vertex] for vertex in cover] + [active])
            cnf.append([-active, unlocked])
        cnf.append([-unlocked] + cover_variables)

    if target > len(unlocked_variables):
        # Preserve a valid UNSAT DIMACS instance even when preprocessing proves
        # that too few candidates can possibly be unlocked.  PySAT's cardinality
        # helper rejects this bound instead of emitting the empty clause.
        cnf.append([])
    else:
        cnf.extend(
            CardEnc.atleast(
                unlocked_variables, target, vpool=pool, encoding=EncType.seqcounter
            ).clauses
        )
    build_seconds = time.monotonic() - started

    with Solver(name=solver_name, bootstrap_with=cnf.clauses) as solver:
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
        f"record_size={len(record)}",
        f"radius={radius}",
        f"target_unlocked={target}",
        f"outside_candidates={len(outside)}",
        f"candidates_with_covers={len(unlocked_variables)}",
        f"minimal_covers={total_covers}",
        f"conflict_edges={total_edges}",
        f"encoding={encoding}",
        f"symmetry_break={symmetry_break}",
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
        actual_unlocked = []
        for candidate_index, edges in enumerate(conflicts):
            if all(int(a) in removal_indices or int(b) in removal_indices for a, b in edges):
                actual_unlocked.append(outside[candidate_index])
        assert len(removal_indices) == radius and len(actual_unlocked) >= target
        lines.extend(
            [
                f"removals={[record[i] for i in sorted(removal_indices)]}",
                f"actual_unlocked_count={len(actual_unlocked)}",
                f"actual_unlocked={actual_unlocked}",
            ]
        )

    output.write_text("\n".join(lines) + "\n")
    print(
        f"status={status} radius={radius} target={target} "
        f"candidates={len(unlocked_variables)} covers={total_covers} "
        f"vars={pool.top} clauses={len(cnf.clauses)} output={output}"
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=100)
    parser.add_argument("--record-json", type=Path)
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--encoding", choices=("edge", "dnf"), default="edge")
    parser.add_argument("--symmetry-break", action="store_true")
    parser.add_argument("--seconds", type=float, default=300.0)
    # Glucose supports PySAT's interrupt API, so the default time limit is reliable.
    parser.add_argument("--solver", default="glucose42")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    solve(
        args.n,
        args.radius,
        args.target,
        args.encoding,
        args.symmetry_break,
        args.seconds,
        args.solver,
        args.output,
        args.record_json,
    )


if __name__ == "__main__":
    main()
