#!/usr/bin/env python3
"""Independent exact verifier for the one-point robustness certificate."""

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = ROOT / "alphaevolve_repository_of_problems/experiments/subsets_of_the_grid_with_no_isosceles_triangles/subsets_of_the_grid_with_no_isosceles_triangles.ipynb"
CERTIFICATE = ROOT / "research/robustness_n100.txt"


def squared_distance(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def load_record():
    notebook = json.loads(NOTEBOOK.read_text())
    source = "\n".join("".join(cell.get("source", [])) for cell in notebook["cells"])
    tail = source.split("sol_100 = ", 1)[1]
    return ast.literal_eval(tail[: tail.index("]") + 1])


def conflict_edges(candidate, record):
    edges = []
    for i, a in enumerate(record):
        candidate_a = squared_distance(candidate, a)
        for b in record[i + 1 :]:
            candidate_b = squared_distance(candidate, b)
            a_b = squared_distance(a, b)
            if candidate_a == candidate_b or candidate_a == a_b or candidate_b == a_b:
                edges.append(frozenset((a, b)))
    return edges


def is_valid(points):
    for apex in points:
        distances = set()
        for other in points:
            if other == apex:
                continue
            distance = squared_distance(apex, other)
            if distance in distances:
                return False
            distances.add(distance)
    return True


def main():
    record = load_record()
    record_set = set(record)
    assert len(record) == len(record_set) == 164
    assert is_valid(record)

    witnesses = []
    for line in CERTIFICATE.read_text().splitlines():
        match = re.fullmatch(r"candidate=(\(\d+,\d+\)) remove=\[(.*)\]", line)
        if not match:
            continue
        candidate = ast.literal_eval(match.group(1))
        removals = ast.literal_eval("[" + match.group(2) + "]")
        witnesses.append((candidate, removals))

    no_cover_of_size_zero_or_one = 0
    for x in range(100):
        for y in range(100):
            candidate = (x, y)
            if candidate in record_set:
                continue
            edges = conflict_edges(candidate, record)
            assert edges
            common = set(edges[0])
            for edge in edges[1:]:
                common.intersection_update(edge)
            assert not common
            no_cover_of_size_zero_or_one += 1

    assert no_cover_of_size_zero_or_one == 10_000 - 164
    assert len(witnesses) == 16
    for candidate, removals in witnesses:
        assert len(removals) == 2 and len(set(removals)) == 2
        assert all(point in record_set for point in removals)
        reduced = [point for point in record if point not in removals]
        assert is_valid(reduced + [candidate])

    print(
        "verified=true record_size=164 outside_points=9836 "
        "minimum_removals=2 attaining_witnesses=16"
    )


if __name__ == "__main__":
    main()
