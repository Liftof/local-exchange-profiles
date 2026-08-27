#!/usr/bin/env python3
"""Stronger SAT decision model for the radius-r local replacement problem.

The original decision encoding asks for *at least* k selector variables.  Here
we ask for exactly k.  This is equisatisfiable: when a removal set unlocks more
than k outside points, any k of them can be selected.  The redundant at-most-k
half gives CDCL substantially more propagation.

This file deliberately imports only the geometry/conflict construction.  It
rebuilds all SAT constraints locally so that experiments do not modify the
published solver scripts.
"""

from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

from pysat.card import CardEnc, EncType
from pysat.formula import CNF, IDPool
from pysat.solvers import Solver

from solve_removal_radius_cpsat import build_conflicts, enumerate_minimal_covers, load_record


def add_lex_leq(cnf: CNF, pool: IDPool, left: list[int], right: list[int], label: int) -> None:
    """Encode left <=lex right with exact prefix-equality variables."""
    equal = pool.id(("lex_equal", label, 0))
    cnf.append([equal])
    for position, (a, b) in enumerate(zip(left, right)):
        # If the preceding prefix is equal, 1/0 is forbidden here.
        cnf.append([-equal, -a, b])

        next_equal = pool.id(("lex_equal", label, position + 1))
        # next_equal -> equal and a == b.
        cnf.append([-next_equal, equal])
        cnf.append([-next_equal, -a, b])
        cnf.append([-next_equal, a, -b])
        # equal and a == b -> next_equal.
        cnf.append([-equal, a, b, next_equal])
        cnf.append([-equal, -a, -b, next_equal])
        equal = next_equal


def add_record_symmetry(cnf: CNF, pool: IDPool, removed: list[int], record: list[tuple[int, int]]) -> None:
    """Keep the lexicographically least member of each C2 x C2 orbit."""
    index = {point: i for i, point in enumerate(record)}
    transforms = (
        lambda p: (99 - p[0], p[1]),
        lambda p: (p[0], 99 - p[1]),
        lambda p: (99 - p[0], 99 - p[1]),
    )
    for label, transform in enumerate(transforms):
        permutation = [index[transform(point)] for point in record]
        add_lex_leq(cnf, pool, removed, [removed[permutation[i]] for i in range(len(record))], label)


def solve(
    radius: int,
    target: int,
    encoding: str,
    symmetry: bool,
    seconds: float,
    solver_name: str,
    output: Path,
) -> None:
    started = time.monotonic()
    record = load_record()
    outside, conflicts, total_edges = build_conflicts(record)

    pool = IDPool()
    cnf = CNF()
    removed = [pool.id(("remove", i)) for i in range(len(record))]
    cnf.extend(CardEnc.equals(removed, radius, vpool=pool, encoding=EncType.seqcounter).clauses)
    if symmetry:
        add_record_symmetry(cnf, pool, removed, record)

    selected: list[int] = []
    total_covers = 0
    for candidate_index, edges in enumerate(conflicts):
        covers = enumerate_minimal_covers(edges, radius)
        if not covers:
            continue
        y = pool.id(("selected", candidate_index))
        selected.append(y)
        total_covers += len(covers)
        if encoding == "edge":
            # y -> every conflict edge is hit by a removed endpoint.
            for a, b in edges:
                cnf.append([-y, removed[int(a)], removed[int(b)]])
        else:
            # y -> at least one explicitly enumerated minimal cover is present.
            cover_vars: list[int] = []
            for cover_index, cover in enumerate(covers):
                z = pool.id(("chosen_cover", candidate_index, cover_index))
                cover_vars.append(z)
                cnf.append([-z, y])
                for vertex in cover:
                    cnf.append([-z, removed[vertex]])
            cnf.append([-y] + cover_vars)

    # Equisatisfiable strengthening of sum(selected) >= target.
    cnf.extend(CardEnc.equals(selected, target, vpool=pool, encoding=EncType.seqcounter).clauses)
    build_seconds = time.monotonic() - started

    with Solver(name=solver_name, bootstrap_with=cnf.clauses) as solver:
        # Prefer choosing target candidates before the removals.  This is only a
        # phase hint and does not affect completeness.
        try:
            solver.set_phases(selected)
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
        "n=100",
        f"record_size={len(record)}",
        f"radius={radius}",
        f"target_selected_exactly={target}",
        f"outside_candidates={len(outside)}",
        f"candidate_selectors={len(selected)}",
        f"minimal_covers={total_covers}",
        f"conflict_edges={total_edges}",
        f"encoding={encoding}",
        f"symmetry_break={symmetry}",
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
        actual_unlocked = [
            outside[i]
            for i, edges in enumerate(conflicts)
            if all(int(a) in removal_indices or int(b) in removal_indices for a, b in edges)
        ]
        selected_indices = [
            i
            for i, edges in enumerate(conflicts)
            if edges.size and pool.obj2id.get(("selected", i), 0) in positive
        ]
        assert len(removal_indices) == radius
        assert len(selected_indices) == target
        assert len(actual_unlocked) >= target
        lines.extend(
            [
                f"removals={[record[i] for i in sorted(removal_indices)]}",
                f"selected={[outside[i] for i in selected_indices]}",
                f"actual_unlocked_count={len(actual_unlocked)}",
                f"actual_unlocked={actual_unlocked}",
            ]
        )

    output.write_text("\n".join(lines) + "\n")
    print(
        f"status={status} radius={radius} target={target} encoding={encoding} "
        f"vars={pool.top} clauses={len(cnf.clauses)} output={output}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius", type=int, required=True)
    parser.add_argument("--target", type=int, required=True)
    parser.add_argument("--encoding", choices=("edge", "cover"), default="edge")
    parser.add_argument("--symmetry-break", action="store_true")
    parser.add_argument("--seconds", type=float, default=300.0)
    parser.add_argument("--solver", default="glucose42")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    solve(
        args.radius,
        args.target,
        args.encoding,
        args.symmetry_break,
        args.seconds,
        args.solver,
        args.output,
    )


if __name__ == "__main__":
    main()
