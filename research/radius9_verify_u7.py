#!/usr/bin/env python3
"""Direct exact-integer verifier for a radius-nine individual-unlock witness."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

from solver_exchange_sat import load_record, verify_no_isosceles


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("witness", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.witness.read_text())
    if data.get("format") != "radius9-individual-unlock-witness-v1":
        raise ValueError("unexpected witness format")

    record = load_record(int(data["n"]))
    removals = [int(index) for index in data["removal_indices"]]
    outsiders = [tuple(map(int, point)) for point in data["individually_unlocked"]]
    if len(removals) != 9 or len(set(removals)) != 9:
        raise AssertionError("expected nine distinct removals")
    if [record[index] for index in removals] != [tuple(p) for p in data["removals"]]:
        raise AssertionError("removal coordinates do not match indices")
    if len(outsiders) != len(set(outsiders)) or set(outsiders) & set(record):
        raise AssertionError("invalid outside-point list")
    retained = [point for index, point in enumerate(record) if index not in set(removals)]
    if not all(verify_no_isosceles(retained + [point]) for point in outsiders):
        raise AssertionError("a claimed outsider is not individually admissible")

    best: tuple[tuple[int, int], ...] = ()
    for size in range(len(outsiders), -1, -1):
        best = next(
            (
                subset
                for subset in itertools.combinations(outsiders, size)
                if verify_no_isosceles(retained + list(subset))
            ),
            (),
        )
        if best:
            break
    expected = [tuple(p) for p in data["best_joint_subset_within_list"]]
    if len(best) != int(data["best_joint_subset_size_within_list"]) or list(best) != expected:
        raise AssertionError("claimed best joint subset differs from exhaustive check")

    result = {
        "format": "radius9-individual-unlock-verification-v1",
        "status": "VERIFIED",
        "witness_sha256": hashlib.sha256(args.witness.read_bytes()).hexdigest(),
        "radius_removed": len(removals),
        "individually_unlocked": len(outsiders),
        "all_individual_integer_geometry_checks": True,
        "subsets_exhaustively_checked": 2 ** len(outsiders),
        "maximum_joint_subset_within_list": len(best),
        "best_joint_subset": best,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(
        f"status=VERIFIED individually_unlocked={len(outsiders)} "
        f"maximum_joint_subset_within_list={len(best)}"
    )


if __name__ == "__main__":
    main()
