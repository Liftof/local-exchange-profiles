#!/usr/bin/env python3
"""Independent CNF generator for the radius-r local-resilience claim.

This file deliberately imports neither NumPy, OR-Tools, PySAT, nor any of the
project's existing research modules.  It reads the public AlphaEvolve notebook,
extracts ``sol_100`` from its Python AST, regenerates every geometric conflict
with plain integer arithmetic, and emits a self-contained DIMACS instance.

The CNF is satisfiable iff there is a set of exactly ``radius`` record points
whose removal makes at least ``target`` outside points individually admissible.
All 9,836 outside candidates are present; no vertex-cover prefilter is trusted.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = (
    ROOT
    / "alphaevolve_repository_of_problems"
    / "experiments"
    / "subsets_of_the_grid_with_no_isosceles_triangles"
    / "subsets_of_the_grid_with_no_isosceles_triangles.ipynb"
)


def squared_distance(a: tuple[int, int], b: tuple[int, int]) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def load_record() -> list[tuple[int, int]]:
    """Extract the unique top-level assignment to sol_100 via Python's AST."""
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    assignments: list[object] = []
    for cell in notebook["cells"]:
        if cell.get("cell_type") != "code":
            continue
        tree = ast.parse("".join(cell.get("source", [])))
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == "sol_100" for target in targets):
                assignments.append(ast.literal_eval(node.value))
    if len(assignments) != 1:
        raise ValueError(f"expected one sol_100 assignment, found {len(assignments)}")
    record = [tuple(point) for point in assignments[0]]
    if len(record) != 164 or len(set(record)) != 164:
        raise ValueError("sol_100 must contain 164 distinct points")
    if any(len(point) != 2 or not all(0 <= coordinate < 100 for coordinate in point) for point in record):
        raise ValueError("sol_100 contains a point outside {0,...,99}^2")
    return record


def validate_record(record: list[tuple[int, int]]) -> None:
    """Check the record directly: distances from every possible apex are unique."""
    for apex_index, apex in enumerate(record):
        seen: dict[int, int] = {}
        for other_index, other in enumerate(record):
            if other_index == apex_index:
                continue
            distance = squared_distance(apex, other)
            if distance in seen:
                raise ValueError(
                    "record contains an isosceles triangle at apex "
                    f"{apex}: {record[seen[distance]]}, {other}"
                )
            seen[distance] = other_index


def build_conflicts(
    record: list[tuple[int, int]],
) -> tuple[list[tuple[int, int]], list[tuple[tuple[int, int], ...]]]:
    """Regenerate H_p with an apex/ring algorithm unlike the NumPy pair scan.

    For each record apex a, ``rings[a][d]`` lists the record points at squared
    distance d from a.  For an outside p, conflicts arise either from two
    record points on one ring around p, or from p and a record point on one
    ring around a record apex.  The union is exactly all pairs {a,b} for which
    {p,a,b} is isosceles.
    """
    record_set = set(record)
    rings: list[dict[int, list[int]]] = []
    for apex_index, apex in enumerate(record):
        by_distance: dict[int, list[int]] = defaultdict(list)
        for other_index, other in enumerate(record):
            if other_index != apex_index:
                by_distance[squared_distance(apex, other)].append(other_index)
        rings.append(by_distance)

    outside: list[tuple[int, int]] = []
    all_edges: list[tuple[tuple[int, int], ...]] = []
    for x in range(100):
        for y in range(100):
            point = (x, y)
            if point in record_set:
                continue
            edges: set[tuple[int, int]] = set()
            around_point: dict[int, list[int]] = defaultdict(list)
            for i, record_point in enumerate(record):
                distance = squared_distance(point, record_point)
                for j in around_point[distance]:
                    edges.add((min(i, j), max(i, j)))
                around_point[distance].append(i)
                for j in rings[i].get(distance, ()):
                    edges.add((min(i, j), max(i, j)))
            outside.append(point)
            all_edges.append(tuple(sorted(edges)))
    return outside, all_edges


def greedy_matching(edges: frozenset[tuple[int, int]]) -> tuple[tuple[int, int], ...]:
    used: set[int] = set()
    matching: list[tuple[int, int]] = []
    for a, b in sorted(edges):
        if a not in used and b not in used:
            used.add(a)
            used.add(b)
            matching.append((a, b))
    return tuple(matching)


def matching_lower_bound(edges: frozenset[tuple[int, int]]) -> int:
    return len(greedy_matching(edges))


def alternative_minimal_covers(
    edge_iterable: Iterable[tuple[int, int]], budget: int
) -> set[tuple[int, ...]]:
    """Enumerate covers using the v-or-all-neighbours branching identity.

    This intentionally differs from the project's edge-endpoint recursion.
    For any vertex v, every vertex cover either contains v or contains every
    neighbour of v.  The routine is only an audit cross-check; the emitted CNF
    does not depend on these covers or on this prefilter.
    """
    original = frozenset(edge_iterable)
    answers: set[tuple[int, ...]] = set()

    def recurse(edges: frozenset[tuple[int, int]], chosen: tuple[int, ...], left: int) -> None:
        if not edges:
            cover = set(chosen)
            for vertex in sorted(tuple(cover)):
                reduced = cover - {vertex}
                if all(a in reduced or b in reduced for a, b in original):
                    cover = reduced
            answers.add(tuple(sorted(cover)))
            return
        if left < 0 or matching_lower_bound(edges) > left:
            return
        neighbours: dict[int, set[int]] = defaultdict(set)
        for a, b in edges:
            neighbours[a].add(b)
            neighbours[b].add(a)
        vertex = max(neighbours, key=lambda item: (len(neighbours[item]), -item))
        adjacent = neighbours[vertex]

        recurse(
            frozenset(edge for edge in edges if vertex not in edge),
            chosen + (vertex,),
            left - 1,
        )
        if len(adjacent) <= left:
            recurse(
                frozenset(
                    edge
                    for edge in edges
                    if edge[0] not in adjacent and edge[1] not in adjacent
                ),
                chosen + tuple(sorted(adjacent)),
                left - len(adjacent),
            )

    recurse(original, (), budget)
    return {cover for cover in answers if len(cover) <= budget}


class Cnf:
    def __init__(self) -> None:
        self.top = 0
        self.clauses: list[tuple[int, ...]] = []

    def new_var(self) -> int:
        self.top += 1
        return self.top

    def add(self, *literals: int) -> None:
        if not literals:
            raise ValueError("unexpected empty clause during generation")
        if len(set(literals)) != len(literals):
            raise ValueError(f"duplicate literal in clause {literals}")
        if any(-literal in literals for literal in literals):
            raise ValueError(f"tautological clause {literals}")
        self.clauses.append(tuple(literals))


def add_threshold_counter(cnf: Cnf, inputs: list[int], cap: int) -> list[int]:
    """Return exact indicators for >=1,...,>=cap true inputs.

    The recurrence is q[i,j] <-> q[i-1,j] OR (q[i-1,j-1] AND x[i]).
    Every direction is encoded, avoiding reliance on a third-party cardinality
    library.  The returned j-th entry is true exactly when at least j+1 inputs
    are true.
    """
    if not inputs or cap < 1:
        raise ValueError("counter needs at least one input and a positive cap")
    previous: list[int] = []
    for i, value in enumerate(inputs, start=1):
        current = [cnf.new_var() for _ in range(min(cap, i))]
        for j, indicator in enumerate(current, start=1):
            old_same = previous[j - 1] if j <= len(previous) else None
            old_lower = previous[j - 2] if j >= 2 else None  # j=1 has true base.
            if j == 1:
                if old_same is None:
                    cnf.add(-indicator, value)
                    cnf.add(-value, indicator)
                else:
                    # indicator <-> old_same OR value
                    cnf.add(-old_same, indicator)
                    cnf.add(-value, indicator)
                    cnf.add(-indicator, old_same, value)
            elif old_same is None:
                # indicator <-> old_lower AND value
                assert old_lower is not None
                cnf.add(-indicator, old_lower)
                cnf.add(-indicator, value)
                cnf.add(-old_lower, -value, indicator)
            else:
                # indicator <-> old_same OR (old_lower AND value)
                assert old_lower is not None
                cnf.add(-old_same, indicator)
                cnf.add(-old_lower, -value, indicator)
                cnf.add(-indicator, old_same, old_lower)
                cnf.add(-indicator, old_same, value)
        previous = current
    return previous


def build_cnf(
    record: list[tuple[int, int]],
    outside: list[tuple[int, int]],
    conflicts: list[tuple[tuple[int, int], ...]],
    radius: int,
    target: int,
    candidate_indices: list[int] | None = None,
) -> tuple[Cnf, list[int], list[int]]:
    if not (0 <= radius <= len(record)):
        raise ValueError("invalid radius")
    if not (1 <= target <= len(outside)):
        raise ValueError("invalid target")
    if candidate_indices is None:
        candidate_indices = list(range(len(outside)))
    cnf = Cnf()
    removed = [cnf.new_var() for _ in record]
    unlocked = [cnf.new_var() for _ in candidate_indices]

    # y_p -> (x_a OR x_b) for every edge {a,b} in H_p.
    # Because all candidates are retained, no cover-enumeration assumption is
    # hidden in the decision instance.
    for candidate_var, candidate_index in zip(unlocked, candidate_indices):
        edges = conflicts[candidate_index]
        for a, b in edges:
            cnf.add(-candidate_var, removed[a], removed[b])

    removal_counter = add_threshold_counter(cnf, removed, radius + 1)
    if radius == 0:
        cnf.add(-removal_counter[0])
    else:
        cnf.add(removal_counter[radius - 1])
        cnf.add(-removal_counter[radius])

    unlocked_counter = add_threshold_counter(cnf, unlocked, target)
    cnf.add(unlocked_counter[target - 1])
    return cnf, removed, unlocked


def canonical_record_sha256(record: list[tuple[int, int]]) -> str:
    payload = json.dumps(record, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()


def write_dimacs(path: Path, cnf: Cnf, comments: list[str]) -> None:
    with path.open("w", encoding="ascii") as handle:
        for comment in comments:
            handle.write(f"c {comment}\n")
        handle.write(f"p cnf {cnf.top} {len(cnf.clauses)}\n")
        for clause in cnf.clauses:
            handle.write(" ".join(map(str, clause)) + " 0\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius", type=int, default=6)
    parser.add_argument("--target", type=int, default=5)
    parser.add_argument("--cnf", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--cross-check-covers", action="store_true")
    parser.add_argument(
        "--prefilter-certified-covers",
        action="store_true",
        help=(
            "retain only candidates for which the independent alternative "
            "cover enumeration finds a cover within the radius"
        ),
    )
    parser.add_argument(
        "--prefilter-matching",
        action="store_true",
        help=(
            "omit only candidates carrying radius+1 pairwise vertex-disjoint "
            "conflict edges, an elementary certificate that radius removals "
            "cannot unlock them"
        ),
    )
    parser.add_argument(
        "--matching-certificate",
        type=Path,
        help="write the explicit disjoint-edge witnesses used by --prefilter-matching",
    )
    args = parser.parse_args()

    record = load_record()
    validate_record(record)
    outside, conflicts = build_conflicts(record)
    total_edges = sum(map(len, conflicts))
    if len(outside) != 9_836:
        raise AssertionError(f"unexpected outside count {len(outside)}")

    cover_stats: dict[str, object] = {}
    candidate_indices: list[int] | None = None
    matching_witnesses: list[dict[str, object]] = []
    if args.prefilter_certified_covers and args.prefilter_matching:
        raise ValueError("choose at most one prefilter")
    if args.cross_check_covers or args.prefilter_certified_covers:
        covers_by_size: dict[int, int] = defaultdict(int)
        candidates_with_covers = 0
        total_covers = 0
        eligible_indices: list[int] = []
        for candidate_index, edges in enumerate(conflicts):
            covers = alternative_minimal_covers(edges, args.radius)
            if covers:
                candidates_with_covers += 1
                eligible_indices.append(candidate_index)
            total_covers += len(covers)
            for cover in covers:
                covers_by_size[len(cover)] += 1
        cover_stats = {
            "candidates_with_covers": candidates_with_covers,
            "minimal_covers": total_covers,
            "minimal_covers_by_size": dict(sorted(covers_by_size.items())),
        }
        if args.prefilter_certified_covers:
            candidate_indices = eligible_indices

    if args.prefilter_matching:
        candidate_indices = []
        for candidate_index, edges in enumerate(conflicts):
            matching = greedy_matching(frozenset(edges))
            if len(matching) >= args.radius + 1:
                witness = matching[: args.radius + 1]
                matching_witnesses.append(
                    {
                        "candidate_index": candidate_index,
                        "candidate": outside[candidate_index],
                        "matching": witness,
                    }
                )
            else:
                candidate_indices.append(candidate_index)
        if args.matching_certificate:
            args.matching_certificate.write_text(
                json.dumps(matching_witnesses, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
    elif args.matching_certificate:
        raise ValueError("--matching-certificate requires --prefilter-matching")

    cnf, removed, unlocked = build_cnf(
        record,
        outside,
        conflicts,
        args.radius,
        args.target,
        candidate_indices=candidate_indices,
    )
    comments = [
        "independent all-candidate local-resilience encoding",
        f"record_sha256={canonical_record_sha256(record)}",
        f"radius={args.radius} target={args.target}",
        f"removed_vars={removed[0]}..{removed[-1]}",
        f"unlocked_vars={unlocked[0]}..{unlocked[-1]}",
    ]
    if args.cnf:
        write_dimacs(args.cnf, cnf, comments)

    manifest: dict[str, object] = {
        "notebook": str(NOTEBOOK.relative_to(ROOT)),
        "notebook_sha256": hashlib.sha256(NOTEBOOK.read_bytes()).hexdigest(),
        "record_sha256": canonical_record_sha256(record),
        "record_size": len(record),
        "record_valid": True,
        "outside_candidates": len(outside),
        "conflict_edges": total_edges,
        "minimum_edges_per_candidate": min(map(len, conflicts)),
        "maximum_edges_per_candidate": max(map(len, conflicts)),
        "radius": args.radius,
        "target": args.target,
        "candidate_prefilter": bool(args.prefilter_certified_covers),
        "matching_prefilter": bool(args.prefilter_matching),
        "matching_exclusion_witnesses": len(matching_witnesses),
        "encoded_candidate_count": len(candidate_indices or outside),
        "cnf_variables": cnf.top,
        "cnf_clauses": len(cnf.clauses),
        **cover_stats,
    }
    if args.cnf:
        manifest["cnf"] = str(args.cnf)
        manifest["cnf_sha256"] = hashlib.sha256(args.cnf.read_bytes()).hexdigest()
    rendered = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    if args.manifest:
        args.manifest.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
