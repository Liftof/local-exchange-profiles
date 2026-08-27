#!/usr/bin/env python3
"""Capture the production core-SAT formula without invoking a SAT solver."""

import argparse
from pathlib import Path

import solver_exchange_core_sat as core


class CaptureSolver:
    output: Path

    def __init__(self, name, bootstrap_with):
        clauses = [tuple(clause) for clause in bootstrap_with]
        top = max(abs(literal) for clause in clauses for literal in clause)
        with self.output.open("w", encoding="ascii") as handle:
            handle.write(f"p cnf {top} {len(clauses)}\n")
            for clause in clauses:
                handle.write(" ".join(map(str, clause)) + " 0\n")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def set_phases(self, phases):
        return None

    def interrupt(self):
        return None

    def solve_limited(self, expect_interrupt=True):
        return None

    def clear_interrupt(self):
        return None

    def accum_stats(self):
        return {}

    def get_model(self):
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair-cache", type=Path, required=True)
    parser.add_argument("--cnf", type=Path, required=True)
    parser.add_argument("--metadata-output", type=Path, required=True)
    parser.add_argument("--symmetry-break", action="store_true")
    args = parser.parse_args()
    CaptureSolver.output = args.cnf
    core.Solver = CaptureSolver
    core.solve(
        n=100,
        radius=7,
        target=6,
        pair_cache=args.pair_cache,
        triple_compatibility=True,
        symmetry=args.symmetry_break,
        seconds=1.0,
        solver_name="capture-only",
        output=args.metadata_output,
    )


if __name__ == "__main__":
    main()
