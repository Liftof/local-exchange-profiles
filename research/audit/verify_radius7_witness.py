#!/usr/bin/env python3
"""Verify the radius-7 lower-bound witness with independent geometry."""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

from independent_cnf import load_record, validate_record


def parse_output(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    return values


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    values = parse_output(args.output)
    if values.get("status") != "SAT":
        raise ValueError("witness output is not SAT")
    if values.get("radius_removed") != "7" or values.get("target_added") != "5":
        raise ValueError("witness output has the wrong radius or target")

    removals = [tuple(point) for point in ast.literal_eval(values["removals"])]
    additions = [tuple(point) for point in ast.literal_eval(values["additions"])]
    if len(removals) != 7 or len(set(removals)) != 7:
        raise ValueError("expected seven distinct removals")
    if len(additions) != 5 or len(set(additions)) != 5:
        raise ValueError("expected five distinct additions")

    record = load_record()
    record_set = set(record)
    if not set(removals) <= record_set:
        raise ValueError("a claimed removal is not a record point")
    if set(additions) & record_set:
        raise ValueError("a claimed addition is already a record point")
    if any(len(point) != 2 or not all(0 <= coordinate < 100 for coordinate in point)
           for point in additions):
        raise ValueError("a claimed addition lies outside the 100 x 100 grid")

    removal_set = set(removals)
    final = [point for point in record if point not in removal_set] + additions
    if len(final) != 162 or len(set(final)) != 162:
        raise ValueError("unexpected final cardinality or duplicate point")
    if int(values["final_size"]) != len(final):
        raise ValueError("reported final size differs from reconstructed size")
    validate_record(final)

    print("radius7_lower_bound_witness_verified=true removals=7 additions=5 final_size=162")


if __name__ == "__main__":
    main()
