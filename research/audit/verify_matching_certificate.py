#!/usr/bin/env python3
"""Small independent checker for radius-6 matching exclusion witnesses.

It intentionally does not import ``independent_cnf`` or any project module.
For every omitted outside candidate, seven vertex-disjoint conflict pairs prove
that six removed record vertices cannot hit all conflicts.
"""

import argparse
import ast
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = (
    ROOT
    / "alphaevolve_repository_of_problems"
    / "experiments"
    / "subsets_of_the_grid_with_no_isosceles_triangles"
    / "subsets_of_the_grid_with_no_isosceles_triangles.ipynb"
)


def load_record():
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    values = []
    for cell in notebook["cells"]:
        if cell.get("cell_type") != "code":
            continue
        for node in ast.parse("".join(cell.get("source", []))).body:
            if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == "sol_100"
                for target in node.targets
            ):
                values.append(ast.literal_eval(node.value))
    if len(values) != 1:
        raise AssertionError(f"found {len(values)} sol_100 assignments")
    return [tuple(point) for point in values[0]]


def distance(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def is_conflict(candidate, a, b):
    sides = (distance(candidate, a), distance(candidate, b), distance(a, b))
    return sides[0] == sides[1] or sides[0] == sides[2] or sides[1] == sides[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("certificate", type=Path)
    parser.add_argument("--radius", type=int, default=6)
    parser.add_argument("--expected-witnesses", type=int, default=9_099)
    args = parser.parse_args()

    record = load_record()
    selected = set(record)
    outside = [
        (x, y)
        for x in range(100)
        for y in range(100)
        if (x, y) not in selected
    ]
    entries = json.loads(args.certificate.read_text(encoding="utf-8"))
    seen_indices = set()
    for entry in entries:
        candidate_index = entry["candidate_index"]
        candidate = tuple(entry["candidate"])
        matching = [tuple(edge) for edge in entry["matching"]]
        assert 0 <= candidate_index < len(outside)
        assert candidate == outside[candidate_index]
        assert candidate_index not in seen_indices
        seen_indices.add(candidate_index)
        assert len(matching) == args.radius + 1
        endpoints = [vertex for edge in matching for vertex in edge]
        assert len(endpoints) == 2 * (args.radius + 1)
        assert len(set(endpoints)) == len(endpoints)
        assert all(0 <= vertex < len(record) for vertex in endpoints)
        assert all(
            a != b and is_conflict(candidate, record[a], record[b])
            for a, b in matching
        )

    assert len(entries) == args.expected_witnesses
    print(
        "verified=true "
        f"matching_witnesses={len(entries)} "
        f"remaining_candidates={len(outside) - len(entries)} "
        f"matching_size={args.radius + 1}"
    )


if __name__ == "__main__":
    main()
